"""切句遗漏、错版审核及无效agent结果不能冒充完成。"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'chinese_sentence_review.py'


class ReviewTests(unittest.TestCase):
    def setUp(self):
        if not SCRIPT.exists():
            self.fail('缺少逐句复核脚本，尚不能生成覆盖清单')
        spec = importlib.util.spec_from_file_location('sentence_review', SCRIPT)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)

    def test_chinese_punctuation_keeps_decimal_citation_and_closing_quote(self):
        raw = '# 标题\n\n她问：“写完了吗？”他点头。剂量是1.5毫克。[³](https://a.test/p?v=1.2)别急……再看一次!\n\n最后一段没有句号\n'
        units = self.m.split_units(raw)
        self.assertEqual([x['original'] for x in units], [
            '# 标题', '她问：“写完了吗？”', '他点头。',
            '剂量是1.5毫克。[³](https://a.test/p?v=1.2)', '别急……', '再看一次!', '最后一段没有句号'])
        self.assertEqual(units[0]['kind'], 'heading')
        for x in units:
            self.assertEqual(raw[x['start']:x['end']], x['original'])

    def test_every_non_whitespace_character_is_covered_in_list_and_code(self):
        raw = '# 题目\n\n- 第一项\n- 第二项。\n\n```python\nx = 1.2\n\nprint("好。")\n```\n\n[参考](https://a.test/a_(b)?q=1)。\n'
        units = self.m.split_units(raw)
        covered = [False] * len(raw)
        for x in units:
            for i in range(x['start'], x['end']):
                self.assertFalse(covered[i], '原文区间重复覆盖')
                covered[i] = True
        self.assertTrue(all(c.isspace() or covered[i] for i,c in enumerate(raw)))
        self.assertEqual(sum(x['kind']=='code' for x in units), 1)
        self.assertIn('print("好。")', next(x['original'] for x in units if x['kind']=='code'))

    def test_ascii_closing_quotes_stay_with_the_sentence(self):
        raw = '她说："不想再陪下去了。"\n\n她说："先跟着老师学。"\n'
        self.assertEqual([u['original'] for u in self.m.split_units(raw)], [
            '她说："不想再陪下去了。"', '她说："先跟着老师学。"'])

    def test_image_alt_and_nested_link_target_are_not_split_into_exclamations(self):
        units=self.m.split_units('![活动照片。](https://a.test/a_(b).png)\n\n请看[这篇报道](https://a.test/a_(b)?x=1.2)。下一句。')
        self.assertEqual([x['original'] for x in units],[
            '![活动照片。](https://a.test/a_(b).png)',
            '请看[这篇报道](https://a.test/a_(b)?x=1.2)。','下一句。'])
        self.assertEqual(units[0]['kind'],'image')

    def make_package(self, root):
        article = root/'article.md'
        article.write_text('# 题目\n\n孩子写完了。妈妈还在检查。\n\n最后一句。\n')
        rules=root/'rules.md'; rules.write_text('语法与口吻分别检查。')
        out=root/'review'
        manifest=self.m.prepare(article,out,reader='家长',style='聊天体',batch_size=2,rules_path=rules,corpus_dir=None)
        return article,out,manifest

    def response(self, manifest, batch):
        rows=[]
        for u in batch['units']:
            rows.append(dict(sentence_id=u['id'],original=u['original'],
                grammar=dict(status='pass',reason='成分完整。'),
                tone=dict(status='pass',reason='用词符合家长日常表达。'),
                coherence=dict(status='pass',reason='主体与前后句一致。'),
                suggestion=u['original'],meaning_risk=False,meaning_note='保留原句。',corpus_refs=[]))
        return dict(review_id=manifest['review_id'],batch_id=batch['batch_id'],results=rows)

    def test_prepare_exposes_full_paragraph_context_and_protects_source(self):
        with tempfile.TemporaryDirectory() as t:
            article,out,m=self.make_package(Path(t))
            packet=json.loads((out/'requests'/'batch-001.json').read_text())
            unit=packet['units'][1]
            self.assertEqual(unit['paragraph'],'孩子写完了。妈妈还在检查。')
            self.assertEqual(unit['next_paragraph'],'最后一句。')
            self.assertIn('家长', (out/'prompts'/'batch-001.md').read_text())
            self.assertEqual((out/'article.snapshot.md').read_bytes(),article.read_bytes())
            with self.assertRaises(ValueError):
                self.m.prepare(article,out,reader='家长',style='聊天体',batch_size=2,rules_path=Path(t)/'rules.md',corpus_dir=None)

    def test_agent_cannot_omit_duplicate_change_original_or_skip_tone(self):
        with tempfile.TemporaryDirectory() as t:
            _,out,m=self.make_package(Path(t))
            b=json.loads((out/'requests'/'batch-001.json').read_text())
            good=self.response(m,b)
            self.m.validate_response(m,b,good)
            mutations=[lambda r:r['results'].pop(),
                lambda r:r['results'].append(r['results'][0]),
                lambda r:r['results'][0].update(original='另一个原句'),
                lambda r:r['results'][0].pop('tone'),
                lambda r:r.update(review_id='过期稿'),
                lambda r:r['results'][0]['tone'].update(reason=''),
                lambda r:r['results'][0]['tone'].update(status=[]),
                lambda r:r['results'][0].update(suggestion='无问题却擅自修改')]
            for mutate in mutations:
                r=json.loads(json.dumps(good)); mutate(r)
                with self.assertRaises(ValueError): self.m.validate_response(m,b,r)

    def test_check_distinguishes_missing_issues_and_complete_and_detects_drift(self):
        with tempfile.TemporaryDirectory() as t:
            article,out,m=self.make_package(Path(t))
            self.assertEqual(self.m.check(out)['state'],'incomplete')
            for path in sorted((out/'requests').glob('*.json')):
                b=json.loads(path.read_text()); r=self.response(m,b)
                (out/'results'/path.name).write_text(json.dumps(r,ensure_ascii=False))
            self.assertEqual(self.m.check(out)['state'],'complete')
            p=out/'results'/'batch-001.json'; r=json.loads(p.read_text())
            r['results'][1]['tone']=dict(status='issue',reason='搭配需要修改。')
            r['results'][1]['suggestion']='孩子已经写完作业了。'
            p.write_text(json.dumps(r,ensure_ascii=False))
            report=self.m.check(out)
            self.assertEqual(report['state'],'complete_with_issues')
            self.assertEqual(report['issue_count'],1)
            self.assertEqual(article.read_text(),'# 题目\n\n孩子写完了。妈妈还在检查。\n\n最后一句。\n')
            article.write_text(article.read_text()+'新增一句。')
            with self.assertRaises(ValueError): self.m.check(out)

    def test_changed_prompt_or_rules_invalidates_review_package(self):
        with tempfile.TemporaryDirectory() as t:
            _,out,_=self.make_package(Path(t))
            prompt=out/'prompts'/'batch-001.md'
            original=prompt.read_bytes();prompt.write_text('绕过检查')
            with self.assertRaises(ValueError): self.m.check(out)
            prompt.write_bytes(original)
            (Path(t)/'rules.md').write_text('规则已有修改')
            with self.assertRaises(ValueError): self.m.check(out)

    def test_run_accepts_each_agent_result_and_resumes_without_calling_again(self):
        # 子进程替身仅模拟CLI协议；不把它的通过结论记作真实agent审稿。
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);article,out,_=self.make_package(root)
            original=article.read_bytes()
            agent=root/'fake-codex'
            agent.write_text('''#!/usr/bin/env python3
import json,sys
from pathlib import Path
assert sys.argv[sys.argv.index('--sandbox')+1]=='read-only'
assert '--ephemeral' in sys.argv
p=json.loads(sys.stdin.read().rsplit('\\n',1)[-1])
rows=[]
for u in p['units']:
 issue=u['id']=='S0002'
 rows.append(dict(sentence_id=u['id'],original=u['original'],
 grammar=dict(status='pass',reason='测试协议：语法结论'),
 tone=dict(status='issue' if issue else 'pass',reason='测试协议：口吻结论'),
 coherence=dict(status='pass',reason='测试协议：承接结论'),
 suggestion='孩子已经写完作业。' if issue else u['original'],
 meaning_risk=False,meaning_note='测试协议，非真实语言判断。',corpus_refs=[]))
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(dict(review_id=p['review_id'],batch_id=p['batch_id'],results=rows),ensure_ascii=False))
''')
            agent.chmod(0o755)
            r=self.m.run(out,codex_bin=str(agent),timeout=5)
            self.assertEqual(r['state'],'complete_with_issues')
            self.assertEqual(r['reviewed_count'],4)
            self.assertEqual(r['issue_count'],1)
            resumed=self.m.run(out,codex_bin=str(root/'nonexistent-agent'),timeout=5)
            self.assertEqual(resumed['reviewed_count'],4)
            self.assertEqual(article.read_bytes(),original)

    def test_missing_reviews_cli_has_nonzero_exit(self):
        with tempfile.TemporaryDirectory() as t:
            _,out,_=self.make_package(Path(t))
            r=subprocess.run([sys.executable,str(SCRIPT),'check',str(out)],capture_output=True,text=True)
            self.assertEqual(r.returncode,2,r.stderr)
            self.assertIn('incomplete',r.stdout)


if __name__=='__main__':unittest.main()
