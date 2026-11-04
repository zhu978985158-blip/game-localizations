from pathlib import Path
import sys,json,io,hashlib,copy
ROOT=Path(__file__).resolve().parents[1]
from fontTools.ttLib import TTFont
from fontTools.subset import Options,Subsetter
from fontTools.ttLib.scaleUpem import scale_upem
src=ROOT/'inputs/魔域争霸简体中文版/font'
dest=ROOT/'交付/魔域争霸_简体中文补全版/font/atroxC.ffa'
rows=json.loads((ROOT/'校验记录/翻译对照.json').read_text())
needed={ord(c) for r in rows for c in r['translation'] if ord(c)>=32}
original=TTFont(src/'atroxC.ffa');donor=TTFont(src/'atroxA.ffa')
missing=needed-set(original.getBestCmap());assert missing<=set(donor.getBestCmap())
options=Options();options.hinting=False
options.drop_tables+=['EBDT','EBLC','EBSC','GSUB','GPOS','GDEF','kern','JSTF']
sub=Subsetter(options=options);sub.populate(unicodes=missing);sub.subset(donor)
if donor['head'].unitsPerEm!=original['head'].unitsPerEm:scale_upem(donor,original['head'].unitsPerEm)
# Append donor glyphs to the original font. This preserves its legacy cmap,
# hinting programs, name records and all original glyph IDs.
merged=copy.deepcopy(original)
donor_order=donor.getGlyphOrder()
rename={name:'zh_'+name for name in donor_order}
assert not (set(rename.values()) & set(merged.getGlyphOrder()))
merged.setGlyphOrder(merged.getGlyphOrder()+[rename[n] for n in donor_order])
for name in donor_order:
 glyph=copy.deepcopy(donor['glyf'][name])
 if glyph.isComposite():
  for component in glyph.components:component.glyphName=rename[component.glyphName]
 merged['glyf'][rename[name]]=glyph
 merged['hmtx'][rename[name]]=donor['hmtx'][name]
for table in merged['cmap'].tables:
 if table.isUnicode():
  for cp in missing:table.cmap[cp]=rename[donor.getBestCmap()[cp]]
merged['maxp'].numGlyphs=len(merged.getGlyphOrder())
merged['OS/2'].recalcUnicodeRanges(merged)
merged['OS/2'].recalcCodePageRanges(merged)
merged['OS/2'].usWinAscent=max(original['OS/2'].usWinAscent,donor['OS/2'].usWinAscent)
merged['OS/2'].usWinDescent=max(original['OS/2'].usWinDescent,donor['OS/2'].usWinDescent)
merged.save(dest)
check=TTFont(dest);oldmap=original.getBestCmap();newmap=check.getBestCmap()
assert needed<=set(newmap)
assert original['head'].unitsPerEm==check['head'].unitsPerEm
for cp,name in oldmap.items():
 newname=newmap[cp]
 assert original['hmtx'][name]==check['hmtx'][newname],f'metric changed {cp}'
 g1=original['glyf'][name];g2=check['glyf'][newname]
 if g1.isComposite():
  # Compare flattened outline coordinates rather than numeric component IDs.
  a=g1.getCoordinates(original['glyf']);b=g2.getCoordinates(check['glyf'])
  assert a==b,(cp,name)
 else:
  assert g1.compile(original['glyf'])==g2.compile(check['glyf']),(cp,name)
report={'font':'atroxC.ffa','original_family':original['name'].getDebugName(1),'original_unicode_count':len(oldmap),'added_characters':len(missing),'added_text':''.join(chr(c) for c in sorted(missing)),'all_original_character_outlines_and_advance_widths_unchanged':True,'new_character_coverage_complete':True,'runtime_rendering_verified':False,'sha256':hashlib.sha256(dest.read_bytes()).hexdigest()}
(ROOT/'校验记录/备用字体补字.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
