from pathlib import Path
import json,re
from xom_language import Language
ROOT=Path(__file__).resolve().parents[1]
TOKEN=r'/\*.*?\*/|%(?:\d+\$)?[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]*[diuoxXfFeEgGaAcspn%]'
tr=json.loads((ROOT/'译文/主语言表.json').read_text());keep=json.loads((ROOT/'译文/技术保留.json').read_text());results=[]
for name in ['English.xom','EngFE.xom','EngLoading.xom','EngLS.xom']:
 items=Language((ROOT/'原始解包/Worms Ultimate Mayhem/Game/Data/Language/PC'/name).read_bytes()).items();source=dict(items)
 translated=tr.get(name,{});retained=keep.get(name,{})
 assert not translated.keys()&retained.keys()
 assert not (translated.keys()|retained.keys())-source.keys()
 for k,v in translated.items():
  assert v.strip() and '蠕虫' not in v,(name,k)
  assert re.findall(TOKEN,source[k])==re.findall(TOKEN,v),(name,k,'control tokens')
  assert source[k].count('\\l')==v.count('\\l'),(name,k,'dialogue segment markers')
  if k=='FE.RandomWormNames':
   assert len(source[k].split(','))==len(v.split(',')),(name,k,'name list size')
   assert all(n.strip() for n in v.split(',')),(name,k,'empty random name')
 results.append({'file':name,'records':len(items),'translated':len(translated),'explicitly_retained':len(retained),'not_yet_classified_or_translated':len(source)-len(translated)-len(retained)})
result={'files':results,'translated_total':sum(r['translated'] for r in results),'errors':[],'scope':'Source text only; does not prove latest build or runtime coverage'}
(ROOT/'验证/译文格式检查.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
