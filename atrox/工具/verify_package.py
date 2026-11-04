from pathlib import Path
import json,struct,re,hashlib,zipfile,sys
from build import ROOT,SRC,DEST,MAIN,HELP,MAP_NAMES,DESCS
from fontTools.ttLib import TTFont
records=ROOT/'校验记录'
sha=lambda b:hashlib.sha256(b).hexdigest()
source=(SRC/'dev/atrox.pak').read_bytes();target=(DEST/'dev/atrox.pak').read_bytes()
entries=json.loads((ROOT/'data/pak目录.json').read_text())
# Independent readback from the original assessment inventory, without writer class.
def read(data,e):
 idx=e['block'];chunks=[];seen=set()
 while True:
  assert idx not in seen
  seen.add(idx);chunks.append(data[512512+idx*2048:512512+(idx+1)*2048])
  idx=struct.unpack_from('<I',data,512+idx*4)[0]
  if idx==0:break
 return b''.join(chunks)[:e['size']]
assert len(source)==len(target)
assert source[:512512]==target[:512512] # Header and allocation table unchanged.
changed=[];states={}
for e in entries:
 a=read(source,e);b=read(target,e)
 if a==b:continue
 name=e['path'];changed.append(name);assert len(a)==len(b)
 if name.endswith('.spm'):
  assert a[:62]==b[:62] and a[1118:]==b[1118:]
  title=b[62:94].split(b'\0')[0].decode('gbk')
  description=b[94:1118].split(b'\0')[0].decode('gbk')
  assert '战役' in title and description==DESCS[Path(name).stem]
 elif name.endswith('gamestr.rts'):
  aa=a.decode('gbk');bb=b.decode('gbk')
  oldvalues=re.findall(r'(?m)^\s*"([^"\r\n]*)"',aa)
  newvalues=re.findall(r'(?m)^\s*"([^"\r\n]*)"',bb)
  assert len(oldvalues)==len(newvalues)
  assert newvalues==[MAIN.get(s,s) for s in oldvalues]
  assert re.findall(r'(?m)^\$\d+',aa)==re.findall(r'(?m)^\$\d+',bb)
  assert re.findall(r'%[a-zA-Z]',aa)==re.findall(r'%[a-zA-Z]',bb)
  states['main_text_rows']=len(newvalues)
 elif name.endswith('lf_help.t2b'):
  assert a[:88]==b[:88]
  decode=lambda data:bytes(((x&0b01010101)<<1)|((x&0b10101010)>>1) for x in data[88:])
  aa=decode(a).decode('cp949');bb=decode(b).decode('gbk')
  oldvalues=re.findall(r'"([^"\r\n]*)"',aa);newvalues=re.findall(r'"([^"\r\n]*)"',bb)
  assert len(oldvalues)==len(newvalues)==22
  for x,y in zip(oldvalues,newvalues):
   assert len(x.encode('cp949'))==len(y.encode('gbk'))
   assert y.strip()==HELP.get(x.strip(),x.strip())
  assert re.findall(r'/\d+',aa)==re.findall(r'/\d+',bb)
  for key in ['F9','A,S,D,F,G','Z,X,C,V,B','Space','0~9','CTRL','Shift']:
   assert aa.count(key)==bb.count(key)
  assert not re.search('[가-힣]',bb)
 else:raise AssertionError(name)
assert len(changed)==28
changed_files=[];manifest={}
for f in sorted(SRC.rglob('*')):
 if not f.is_file():continue
 rel=f.relative_to(SRC);a=f.read_bytes();b=(DEST/rel).read_bytes()
 if a!=b:changed_files.append(str(rel))
 if rel.parts[0]=='maps':
  assert a[:62]==b[:62] and a[94:]==b[94:]
  assert b[62:94].split(b'\0')[0].decode('gbk')==MAP_NAMES[f.name]
expected={'dev/atrox.pak','font/atroxC.ffa'}|{'maps/'+n for n in MAP_NAMES}
assert set(changed_files)==expected
rows=json.loads((records/'翻译对照.json').read_text());assert len(rows)==109
needed={ord(c) for r in rows for c in r['translation'] if ord(c)>=32}
font_results=[]
for f in (DEST/'font').glob('*.ffa'):
 font=TTFont(f,checkChecksums=2);cmap=font.getBestCmap()
 assert needed<=set(cmap),(f.name,needed-set(cmap))
 font_results.append({'font':f.name,'missing_new_characters':0,'glyphs':len(cmap)})
 # Force a full compile to validate composite references and all tables.
 import io
 font.save(io.BytesIO())
(records/'字体覆盖检查_最终.json').write_text(json.dumps(font_results,ensure_ascii=False,indent=2))
for f in sorted(DEST.rglob('*')):
 if f.is_file():manifest[str(f.relative_to(DEST))]={'size':f.stat().st_size,'sha256':sha(f.read_bytes())}
(records/'交付文件清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
result={'status':'static_checks_passed','translation_fields':len(rows),'all_archive_objects_checked':len(entries),'archive_objects_modified':len(changed),'archive_objects_unchanged':len(entries)-len(changed),'modified_files':changed_files,'archive_size_and_allocation_table_unchanged':True,'all_map_gameplay_and_story_bytes_unchanged':True,'main_string_order_and_placeholders_unchanged':True,'help_field_widths_and_formatting_codes_unchanged':True,'all_fonts_cover_new_characters':True,'windows_runtime_verified':False,'images_and_videos_translated':False,'original_rar_sha256':sha((ROOT/'inputs/魔域争霸简体中文版.rar').read_bytes())}
(records/'最终校验.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False))
# Full game plus a smaller patch for existing installations.
archives=[]
full=ROOT/'交付/魔域争霸_简体中文补全版.zip'
patch=ROOT/'交付/魔域争霸_中文补全补丁.zip'
for zpath,ispatch in [(full,False),(patch,True)]:
 assert not zpath.exists()
 with zipfile.ZipFile(zpath,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
  if ispatch:
   for rel in sorted(expected):z.write(DEST/rel,rel)
   instruction='''这是给你之前那个版本用的补汉化补丁。\r\n\r\n先关掉游戏，把原来的游戏文件夹备份一份。\r\n把补丁里的 dev、font、maps 三个文件夹复制到 atrox.exe 所在的文件夹，提示同名文件就选替换，然后打开游戏就行。\r\n\r\n有文字显示不对的地方，截图发我。想换回原版就用之前备份的文件。\r\n'''
   z.writestr('使用说明.txt',instruction.encode('utf-8-sig'))
  else:
   for rel in manifest:z.write(DEST/rel,DEST.name+'/'+rel)
 with zipfile.ZipFile(zpath) as z:
  assert z.testzip() is None
  for n in z.namelist():
   if ispatch and n=='使用说明.txt':continue
   rel=n if ispatch else n[len(DEST.name)+1:]
   assert sha(z.read(n))==manifest[rel]['sha256']
 archives.append({'file':zpath.name,'bytes':zpath.stat().st_size,'sha256':sha(zpath.read_bytes()),'crc_and_content_hashes_verified':True})
 print('PACKAGED',zpath.name,zpath.stat().st_size,flush=True)
(records/'压缩包校验.json').write_text(json.dumps(archives,ensure_ascii=False,indent=2))
