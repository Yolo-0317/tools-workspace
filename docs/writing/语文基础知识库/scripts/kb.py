"""本地语文知识查询；召回候选用法，不自动判定句子或改写正文。"""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUSES = {'候选', '待核', '有争议', '已核', '停用'}
EVIDENCE = {'编辑归纳', '辞书释义', '语料观察', '用户局部偏好'}
READ = {'full_entry_read', 'prior_full_entry_read', 'selected_definitions_read', 'selected_sense_excerpts_read'}


def validate(entries, sources):
    def require(condition, message):
        if not condition:
            raise ValueError(message)
    source_map = {s['id']: s for s in sources}
    require(len(source_map) == len(sources), '来源ID重复')
    ids, forms, senses = set(), set(), set()
    for e in entries:
        require(e['id'] not in ids, '词条ID重复: ' + e['id'])
        require(e['lemma'] not in forms, '词形重复: ' + e['lemma'])
        ids.add(e['id']); forms.add(e['lemma'])
        require(e['status'] in STATUSES and bool(e['scope']), '词条状态或范围不全')
        require(bool(e['senses']), '义项为空')
        for sense in e['senses']:
            require(sense['id'] not in senses, '义项ID重复: ' + sense['id'])
            senses.add(sense['id'])
            require(sense['status'] in STATUSES and bool(sense['meaning']), '义项状态或释义不全')
            require(e['status'] != '已核' or sense['status'] == '已核', '已核词条中含待核/争议义项')
            require(bool(sense['source_ids']), '义项缺来源')
            for sid in sense['source_ids']:
                require(sid in source_map, '不存在的来源: ' + sid)
                if sense['status'] == '已核':
                    require(source_map[sid]['read_status'] in READ, '阅读范围不足以支持已核义项: ' + sid)
            require(bool(sense['usages']), '义项缺用法')
            for usage in sense['usages']:
                require(usage['evidence_type'] in EVIDENCE, '未知证据类别')
                require(usage['example_type'] in {'自编', '语料', '用户改稿'}, '未知例句类型')
                require(all(usage.get(k) for k in ('context', 'example', 'risk')), '语境、例句或风险为空')
                if usage['evidence_type'] == '语料观察' or usage['example_type'] == '语料':
                    require(bool(usage.get('corpus_source_id')), '语料例句缺来源')
    return True


def lookup(entries, text, mode='word', include_pending=False):
    active = [e for e in entries if e['status'] != '停用' and (include_pending or e['status'] == '已核')]
    forms = defaultdict(list)
    for e in active:
        for form in [e['lemma'], *e.get('aliases', [])]:
            forms[form].append(e)
    if mode == 'word':
        return forms.get(text, [])
    if mode == 'tag':
        return [e for e in active if text in e.get('tags', []) or text in e.get('groups', [])]
    if mode != 'sentence':
        raise ValueError('未知查询模式')
    # 已知词形内最长匹配，不能替代真正分词或义项判断。
    boundaries = set(forms)
    for e in entries:
        if e['status'] != '停用':
            boundaries.update([e['lemma'], *e.get('aliases', [])])
    ordered = sorted(boundaries, key=lambda s: (-len(s), s))
    found, seen, position = [], set(), 0
    while position < len(text):
        match = next((f for f in ordered if text.startswith(f, position)), None)
        if match:
            for e in forms[match]:
                if e['id'] not in seen:
                    found.append(e); seen.add(e['id'])
            position += len(match)
        else:
            position += 1
    return found


def make_index(entries):
    words, aliases, tags, groups = (defaultdict(list) for _ in range(4))
    for e in entries:
        words[e['lemma']].append(e['id'])
        for name, target in [('aliases', aliases), ('tags', tags), ('groups', groups)]:
            for value in e.get(name, []):
                target[value].append(e['id'])
    return {'schema_version': 1, 'words': dict(words), 'aliases': dict(aliases),
            'tags': dict(tags), 'groups': dict(groups),
            'counts': {'entries': len(entries),
                       'reviewed_entries': sum(e['status'] == '已核' for e in entries),
                       'senses': sum(len(e['senses']) for e in entries),
                       'reviewed_senses': sum(s['status'] == '已核' for e in entries for s in e['senses']),
                       'usages': sum(len(s['usages']) for e in entries for s in e['senses']),
                       'states': dict(Counter(e['status'] for e in entries))}}


def render(entries, sources):
    source_map = {s['id']: s for s in sources}
    lines = [f'# {len(entries)}词用法参考', '',
             '由data中的结构化内容生成，请勿直接改本页。仅覆盖各词声明的义项；“已核”指本批所列知识经来源核对，不代表全部义项、独立专家评审或写作效果验证。', '',
             '例句均按条目标记。编辑归纳不是辞书原文，也不是统一替换规则。', '']
    for e in entries:
        lines.extend([f"## {e['lemma']}", '', f"`{e['id']}` · {e['status']} · {e.get('pronunciation', '读音见来源')} · 范围：{e['scope']}", '',
                      '标签：' + '、'.join(e.get('tags', [])), ''])
        if e.get('notes'):
            lines.extend([e['notes'], ''])
        for s in e['senses']:
            lines.extend([f"### {s['id']} · {s['pos']} · {s['meaning']}", '',
                          '依据：' + '；'.join(f"[{sid}]({source_map[sid]['url']})" for sid in s['source_ids']), ''])
            for u in s['usages']:
                lines.extend([f"- 语境：{u['context']}", f"- 例句（{u['example_type']}）：{u['example']}",
                              f"- 解释性质：{u['evidence_type']}", f"- 边界：{u['risk']}"])
                if u.get('comparison'):
                    lines.append('- 比较：' + u['comparison'])
                lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def load(root=ROOT):
    registry = json.loads((root / 'sources/registry.json').read_text())
    entries = []
    for p in sorted((root / 'data').glob('batch-*.json')):
        entries.extend(json.loads(p.read_text())['entries'])
    validate(entries, registry['sources'])
    return entries, registry['sources']


def build(root=ROOT):
    entries, sources = load(root)
    index = make_index(entries)
    index['source_files'] = [str(p.relative_to(root)) for p in sorted((root / 'data').glob('batch-*.json'))]
    index_path = root / 'indexes/lexicon.json'
    index_path.parent.mkdir(exist_ok=True); (root / 'views').mkdir(exist_ok=True)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2) + '\n')
    navigation = ['# 分批用法参考', '', '各批次从同名JSON生成；数量为词目数，不代表全部义项已建齐。', '']
    for data_path in sorted((root / 'data').glob('batch-*.json')):
        batch = json.loads(data_path.read_text())['entries']
        view_path = root / 'views' / (data_path.stem + '.md')
        view_path.write_text(render(batch, sources))
        navigation.append(f'- [{data_path.stem}：{len(batch)}词]({view_path.name})')
    (root / 'views/README.md').write_text('\n'.join(navigation) + '\n')
    return index['counts']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('build', help='校验并生成索引和阅读页')
    sub.add_parser('check', help='校验词条、状态及来源引用')
    query = sub.add_parser('query', help='返回候选词义，不自动替换正文')
    query.add_argument('text')
    query.add_argument('--mode', choices=['word', 'sentence', 'tag'], default='word')
    query.add_argument('--context', default='', help='随结果保留的上下文；程序不据此自动判义')
    query.add_argument('--include-pending', action='store_true')
    args = parser.parse_args()
    try:
        if args.command == 'build':
            result = build()
        else:
            entries, _ = load()
            if args.command == 'check':
                result = make_index(entries)['counts']
            else:
                result = {'query': args.text, 'context': args.context,
                          'warning': '仅召回候选，未判义、未改稿；未建多字词可能造成短字误命中，须连上下文核对。',
                          'entries': lookup(entries, args.text, args.mode, args.include_pending)}
    except (ValueError, KeyError) as exc:
        parser.exit(1, f'知识库校验失败：{exc}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
