import copy
import importlib.util
from pathlib import Path
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'scripts' / 'kb.py'
spec = importlib.util.spec_from_file_location('chinese_kb', MODULE)
kb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(kb)


def entry(lemma, identifier, status='已核'):
    return {'id': identifier, 'lemma': lemma, 'aliases': [], 'status': status,
            'scope': '仅所列常用义项', 'tags': ['持续'], 'groups': ['持续组'],
            'senses': [{'id': identifier + '.1', 'pos': '副词', 'meaning': '状态持续',
                        'source_ids': ['S1'], 'status': status,
                        'usages': [{'context': '前文已有状态', 'example': '读了以后还是没懂。',
                                    'example_type': '自编', 'evidence_type': '编辑归纳',
                                    'risk': '不补造持续经历'}]}]}


def initial_status_snapshot(entries):
    """仅还原初建阶段的启用状态；历史用例不冒充当前验收结果。"""
    import json
    pending = set(json.loads((kb.ROOT / 'evaluation/baseline-status-1000.json').read_text())['pending_entry_ids'])
    snapshot = copy.deepcopy(entries)
    for e in snapshot:
        if e['id'] in pending:
            e['status'] = '待核'
            for sense in e['senses']:
                sense['status'] = '待核'
    return snapshot


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.entries = [entry('还', 'W1'), entry('还是', 'W2'), entry('了解', 'W3'), entry('了', 'W4')]
        self.sources = [{'id': 'S1', 'url': 'https://example.org/source', 'read_status': 'full_entry_read'}]

    def test_duplicate_id_rejected(self):
        data = self.entries + [copy.deepcopy(self.entries[0])]
        with self.assertRaisesRegex(ValueError, '重复'):
            kb.validate(data, self.sources)

    def test_dangling_source_rejected(self):
        self.entries[0]['senses'][0]['source_ids'] = ['missing']
        with self.assertRaisesRegex(ValueError, '来源'):
            kb.validate(self.entries, self.sources)

    def test_search_summary_cannot_support_reviewed_sense(self):
        self.sources[0]['read_status'] = 'search_summary_only'
        with self.assertRaisesRegex(ValueError, '阅读'):
            kb.validate(self.entries, self.sources)

    def test_selected_definitions_read_supports_scoped_sense(self):
        self.sources[0]['read_status'] = 'selected_definitions_read'
        self.assertTrue(kb.validate(self.entries, self.sources))

    def test_selected_sense_excerpts_support_only_scoped_meaning(self):
        self.sources[0]['read_status'] = 'selected_sense_excerpts_read'
        self.assertTrue(kb.validate(self.entries, self.sources))

    def test_reviewed_entry_cannot_hide_pending_sense(self):
        self.entries[0]['senses'][0]['status'] = '待核'
        with self.assertRaisesRegex(ValueError, '待核'):
            kb.validate(self.entries, self.sources)

    def test_exact_lookup_does_not_expand_substrings(self):
        result = kb.lookup(self.entries, '还', mode='word')
        self.assertEqual([e['lemma'] for e in result], ['还'])

    def test_sentence_uses_longest_known_surface(self):
        result = kb.lookup(self.entries, '他还是不了解。', mode='sentence')
        self.assertEqual([e['lemma'] for e in result], ['还是', '了解'])

    def test_pending_excluded_unless_requested(self):
        self.entries[0]['status'] = '待核'
        self.assertEqual(kb.lookup(self.entries, '还', mode='word'), [])
        self.assertEqual(len(kb.lookup(self.entries, '还', mode='word', include_pending=True)), 1)

    def test_pending_compound_does_not_fall_back_to_short_reviewed_word(self):
        data = [entry('听', 'T1'), entry('听到', 'T2', '待核')]
        self.assertEqual(kb.lookup(data, '听到铃声', mode='sentence'), [])
        self.assertEqual([e['lemma'] for e in kb.lookup(data, '听到铃声', mode='sentence', include_pending=True)], ['听到'])
        self.assertEqual([e['lemma'] for e in kb.lookup(data, '听', mode='word')], ['听'])

    def test_alias_and_multi_sense_preserved(self):
        self.entries[1]['aliases'] = ['還是']
        self.entries[1]['senses'].append(copy.deepcopy(self.entries[1]['senses'][0]))
        self.entries[1]['senses'][1]['id'] = 'W2.2'
        result = kb.lookup(self.entries, '還是', mode='word')
        self.assertEqual(len(result[0]['senses']), 2)

    def test_unknown_is_empty_not_guessed(self):
        self.assertEqual(kb.lookup(self.entries, '术语未收录', mode='word'), [])

    def test_index_status_counts_and_generated_content(self):
        self.entries[0]['status'] = '待核'
        index = kb.make_index(self.entries)
        self.assertEqual(index['counts']['entries'], 4)
        self.assertEqual(index['counts']['reviewed_entries'], 3)
        self.assertEqual(index['words']['还是'], ['W2'])
        markdown = kb.render(self.entries, self.sources)
        self.assertIn('状态持续', markdown)
        self.assertIn('编辑归纳', markdown)
        self.assertIn('https://example.org/source', markdown)

    def test_invalid_evidence_kind_rejected(self):
        self.entries[0]['senses'][0]['usages'][0]['evidence_type'] = '我觉得是词典原文'
        with self.assertRaisesRegex(ValueError, '证据'):
            kb.validate(self.entries, self.sources)


class ActualDataTests(unittest.TestCase):
    def test_sample_has_twenty_entries_with_valid_sources(self):
        entries, sources = kb.load()
        self.assertGreaterEqual(len(entries), 20)
        self.assertGreaterEqual(sum(len(e['senses']) for e in entries), 48)
        self.assertTrue(kb.validate(entries, sources))

    def test_generated_views_match_current_data(self):
        entries, sources = kb.load()
        import json
        for data_path in sorted((kb.ROOT / 'data').glob('batch-*.json')):
            batch = json.loads(data_path.read_text())['entries']
            self.assertEqual((kb.ROOT / 'views' / (data_path.stem + '.md')).read_text(), kb.render(batch, sources))
        index = json.loads((kb.ROOT / 'indexes/lexicon.json').read_text())
        index.pop('source_files')
        self.assertEqual(index, kb.make_index(entries))

    def test_actual_polysemy_and_known_compounds(self):
        entries, _ = kb.load()
        result = kb.lookup(entries, '他还是不了解。', 'sentence')
        self.assertEqual([e['lemma'] for e in result], ['他', '还是', '不', '了解'])
        self.assertEqual(len(result[1]['senses']), 3)

    def test_expansion_queries_and_all_exact_words(self):
        import json
        entries, sources = kb.load()
        self.assertGreaterEqual(len(entries), 200)
        for e in entries:
            expected = [e['id']] if e['status'] == '已核' else []
            self.assertEqual([x['id'] for x in kb.lookup(entries, e['lemma'])], expected, e['lemma'])
        cases = json.loads((kb.ROOT / 'evaluation/cases-200.json').read_text())
        historical = initial_status_snapshot(entries)
        for c in cases:
            self.assertEqual([e['lemma'] for e in kb.lookup([e for e in historical if int(e['id'][1:]) <= 200], c['text'], 'sentence')], c['expected_candidate_words'], c['id'])

    def test_thousand_word_manifest_examples_and_queries(self):
        import json
        entries, sources = kb.load()
        manifest = json.loads((kb.ROOT / 'data/manifest-1000.json').read_text())
        by_id = {e['id']: e for e in entries}
        self.assertEqual(len(manifest['words']), 1000)
        self.assertEqual(len(set(manifest['words'])), 1000)
        self.assertEqual([by_id[i]['lemma'] for i in manifest['entry_ids']], manifest['words'])
        for e in entries:
            for sense in e['senses']:
                for usage in sense['usages']:
                    if int(e['id'][1:]) > 200:
                        self.assertIn(e['lemma'], usage['example'], e['id'])
                        self.assertNotIn('待填写', sense['meaning'])
        cases = json.loads((kb.ROOT / 'evaluation/cases-1000.json').read_text())
        historical = initial_status_snapshot(entries)
        for case in cases:
            self.assertEqual([e['lemma'] for e in kb.lookup(historical, case['text'], 'sentence')], case['expected_candidate_words'], case['id'])

    def test_completed_thousand_words_have_read_evidence(self):
        entries, sources = kb.load()
        source_map = {s['id']: s for s in sources}
        self.assertEqual(len(entries), 1000)
        self.assertTrue(all(e['status'] == '已核' for e in entries))
        self.assertEqual(sum(len(e['senses']) for e in entries), 1028)
        for e in entries:
            self.assertNotIn('默认不参与', e.get('notes', ''), e['id'])
            for sense in e['senses']:
                for sid in sense['source_ids']:
                    self.assertFalse(sid.startswith('PENDING26-'), e['id'])
                    source = source_map[sid]
                    for field in ('url', 'version', 'read_scope', 'checked_at'):
                        self.assertTrue(source.get(field), (e['id'], field))

    def test_completion_queries_keep_current_and_historical_results_separate(self):
        import json
        entries, _ = kb.load()
        cases = json.loads((kb.ROOT / 'evaluation/cases-reviewed-1000.json').read_text())
        for case in cases:
            actual = [e['lemma'] for e in kb.lookup(entries, case['text'], case['mode'])]
            self.assertEqual(actual, case['expected_candidate_words'], case['id'])

    def test_completion_evidence_points_to_real_selected_headwords(self):
        import json
        entries, sources = kb.load()
        source_map = {s['id']: s for s in sources}
        evidence = json.loads((kb.ROOT / 'sources/evidence/cedict-selection-50.json').read_text())
        lines = {r['line']: r for r in evidence['entries']}
        receipt = json.loads((kb.ROOT / 'evaluation/50词补核证据.json').read_text())['entries']
        self.assertEqual(len(receipt), 50)
        for item in receipt:
            cc = [source_map[sid] for sid in item['source_ids'] if sid.startswith('CC26-')]
            if item['lemma'] == '补上':
                self.assertFalse(cc)
                self.assertEqual(source_map['ZD26-W0721']['source_match'], 'related_entry_explicit_gloss')
            else:
                self.assertEqual(len(cc), 1)
                self.assertTrue(cc[0]['lines'])
                self.assertEqual(cc[0]['archive_sha256'], evidence['sha256'])
                for number in cc[0]['lines']:
                    self.assertEqual(lines[number]['simplified'], item['lemma'])
                    self.assertFalse(lines[number]['gloss'].startswith('variant of'))

    def test_reading_specific_particle_sources(self):
        entries, _ = kb.load()
        by_word = {e['lemma']: e for e in entries}
        self.assertEqual(by_word['了']['senses'][0]['source_ids'], ['D13268'])
        self.assertEqual(by_word['吧']['senses'][0]['source_ids'], ['D103'])


class MultiBatchTests(unittest.TestCase):
    def test_build_keeps_each_batch_in_separate_view(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'data').mkdir(); (root / 'sources').mkdir()
            one, two = entry('词一', 'A'), entry('词二', 'B')
            for name, item in [('batch-001', one), ('batch-002', two)]:
                (root / 'data' / (name + '.json')).write_text(json.dumps({'entries': [item]}))
            (root / 'sources/registry.json').write_text(json.dumps({'sources': self_sources()}))
            counts = kb.build(root)
            self.assertEqual(counts['entries'], 2)
            self.assertIn('词一', (root / 'views/batch-001.md').read_text())
            self.assertNotIn('词二', (root / 'views/batch-001.md').read_text())
            self.assertIn('词二', (root / 'views/batch-002.md').read_text())
            self.assertTrue((root / 'views/README.md').exists())


def self_sources():
    return [{'id': 'S1', 'url': 'https://example.org/source', 'read_status': 'full_entry_read'}]


if __name__ == '__main__':
    unittest.main()
