from pathlib import Path
import json, zipfile
p=Path(__file__).resolve().parents[1]
rows=[]
# Names and map display text.
countries=[("Россия","俄罗斯"),("Украина","乌克兰"),("Украина(Life)","乌克兰(Life)"),("Казахстан","哈萨克斯坦"),("Латвия","拉脱维亚"),("Литва","立陶宛"),("Эстония","爱沙尼亚"),("Армения","亚美尼亚"),("Азербайджан","阿塞拜疆"),("Таджикистан","塔吉克斯坦"),("Киргизия","吉尔吉斯斯坦")]
rows.extend(countries)
rows += [(r["ru"],r["zh"]) for r in json.loads((p/"文本/地图名称_中文.json").read_text())]
rows += [(r["俄文"],r["中文"]) for r in json.loads((p/"文本/地图目标_中文.json").read_text())]
# Map dialogues are byte strings built from map data and passed to d.a(String).
# Include every non-empty main resource entry so no visible dialogue falls back to Russian.
with zipfile.ZipFile(next((p/"原版").glob("*.jar"))) as z:
    for name in ("d0","s0","t0"):
        old=z.read("0/"+name).decode("cp1251").split("|")
        new=(p/"文本"/(name+"_中文.txt")).read_text().split("\n")
        if len(old)!=len(new): raise SystemExit(f"slot mismatch {name}: {len(old)} != {len(new)}")
        rows += [(a,b) for a,b in zip(old,new) if a and b and a!=b]
# Preserve first occurrence order while removing duplicate source keys.
uniq=[]; seen=set()
for ru,cn in rows:
    if ru not in seen:
        seen.add(ru); uniq.append((ru,cn))
rows=uniq
q=lambda x:json.dumps(x,ensure_ascii=True)
keys=[]; vals=[]
for ru,cn in rows:
    for key in (ru,ru.encode("cp1251").decode("latin1")):
        keys.append(key); vals.append(cn)
s="""/** Display-only localization: never changes resource or RMS bytes. */
public final class ZhDynamic {
 private static final String[] KEYS = new String[]{%s};
 private static final String[] VALUES = new String[]{%s};
 public static String translate(String text) {
  for(int i=0;i<KEYS.length;i++) if(KEYS[i].equals(text)) return VALUES[i];
  return text;
 }
}
""" % (','.join(map(q,keys)),','.join(map(q,vals)))
(p/"源码").mkdir(exist_ok=True)
(p/"源码/ZhDynamic.java").write_text(s)
(p/"文本/动态显示译表.json").write_text(json.dumps([{"source":a,"zh":b} for a,b in rows],ensure_ascii=False,indent=2)+"\n")
print("Generated",len(rows),"translations;",len(keys),"exact keys")
