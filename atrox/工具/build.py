from pathlib import Path
import struct, re, json, hashlib, shutil
ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'inputs/魔域争霸简体中文版'
DEST=ROOT/'交付/魔域争霸_简体中文补全版'
BASE=512512; BLOCK=2048
class Pak:
 def __init__(self,data):
  self.data=bytearray(data);self.entries={};self.visited=set();self.walk(0,'')
 def chain(self,idx):
  result=[];seen=set()
  while True:
   assert idx not in seen, 'cyclic chain'
   seen.add(idx); assert BASE+(idx+1)*BLOCK<=len(self.data)
   result.append(idx);idx=struct.unpack_from('<I',self.data,512+idx*4)[0]
   if not idx: return result
 def walk(self,idx,path):
  assert idx not in self.visited
  self.visited.add(idx)
  for blk in self.chain(idx):
   for i in range(16):
    pos=BASE+blk*BLOCK+i*128;r=self.data[pos:pos+128]
    if r[0]!=1:continue
    name=r[1:90].split(b'\0')[0].decode('gbk')
    if name in ('.','..'):continue
    block,size,_,attr=struct.unpack_from('<IIII',r,112)
    full=path+'/'+name
    if attr==1:self.walk(block,full)
    else:
     assert full not in self.entries
     self.entries[full]={'block':block,'size':size,'entry_pos':pos,'attr':attr}
 def read(self,name):
  e=self.entries[name]
  raw=b''.join(self.data[BASE+i*BLOCK:BASE+(i+1)*BLOCK] for i in self.chain(e['block']))
  assert len(raw)>=e['size'];return bytes(raw[:e['size']])
 def write_same_size(self,name,content):
  e=self.entries[name];assert len(content)==e['size']
  for j,blk in enumerate(self.chain(e['block'])):
   chunk=content[j*BLOCK:(j+1)*BLOCK]
   self.data[BASE+blk*BLOCK:BASE+blk*BLOCK+len(chunk)]=chunk

def swap_bits(data):return bytes(((x&0x55)<<1)|((x&0xaa)>>1) for x in data)
def sha(data):return hashlib.sha256(data).hexdigest()
MAIN={
 'Unknown':'未知','Black':'黑色','Blue':'蓝色','Emerald':'翠绿色','Fawn':'黄褐色',
 'Green':'绿色','Invalid file':'无效文件','Loading':'载入中','Modem connection':'拨号连接',
 'Orange':'橙色','Purple':'紫色','Red':'红色','Rush Zone':'对战专区','Serial connection':'串口连接',
 'Skyblue':'天蓝色','White':'白色','Yellow':'黄色','exp':'经验','kill':'击杀','level':'等级',
 'slot down':'槽位下移','slot up':'槽位上移',
}
HELP={
 '/4메뉴 단축키':'/4菜单快捷键',
 '/4단축키':'/4快捷键',
 '(아이콘 윗줄)  /9A,S,D,F,G':'（图标上排）/9A,S,D,F,G',
 '(아이콘 아랫줄)/9Z,X,C,V,B':'（图标下排）/9Z,X,C,V,B',
 '/4그룹 지정':'/4设置编队',
 '/4그룹선택':'/4选择编队',
 '/4복수 선택':'/4多选单位',
 '/9마우스 왼쪽버튼 더블 클릭':'/9双击鼠标左键',
 '또는 /9CTRL+마우스 왼쪽버튼':'或 /9CTRL+鼠标左键',
 '/4랠리 포인트 지정':'/4设置集结点',
 '/9생산 건물 선택 후 마우스 오른쪽 버튼 클릭.':'/9选中生产建筑后，单击鼠标右键',
 '/4진형 생성 및 크기 조절':'/4设置阵型与大小',
 '/9유니트들을 선택 후 진형 버튼 클릭':'/9选中单位后，单击阵型按钮',
 '/9E와 R키로 진형 크기를 조정':'/9按E和R键调整阵型大小',
 '/4매크로 기능':'/4连续指令',
 '/9Shift버튼을 누른 상태에서 연속 명령':'/9按住Shift键，连续下达指令',
}
DESCS={
 'createse01':'摧毁人类的所有基地！',
 'createse02':'取得奈力乌斯矿石。',
 'createse03':'摧毁使徒族的所有基地！',
 'createse04':'守住基地，直到李卡特撤离！',
 'createse05':'摧毁使徒族的所有基地！',
 'createse06':'在24分钟内摧毁敌军的所有基地！',
 'createse07':'救出巴仑佳！',
 'createse08':'摧毁人类的所有基地！',
 'createse09':'摧毁使徒族的所有基地！',
 'hominian01':'找到敌军的母体并将其摧毁！',
 'hominian02a':'抵挡敌军的攻击，坚持13分钟！',
 'hominian02b':'护送洛克尼安全抵达水下都市入口！',
 'hominian03':'侦察敌军战舰的位置，\r\n歼灭敌军的侦察部队。',
 'hominian04':'摧毁使徒族的所有基地！',
 'hominian05':'解除七道封印，\r\n摧毁中央防御基地！',
 'hominian06':'摧毁使徒族的基地！',
 'hominian07':'在30分钟内摧毁空间输送系统！',
 'hominian08':'摧毁使徒族的基地！',
 'intelion01':'从迫降的运输舰中\r\n取得外星生物样本！',
 'intelion02':'摧毁人类的所有基地！',
 'intelion03':'摧毁德尔塔003地区\r\n异魔族的所有基地！',
 'intelion04':'摧毁德尔塔003地区\r\n异魔族的所有基地！',
 'intelion05':'让奈顿抵达空间输送系统！',
 'intelion06':'摧毁异魔族的中央防御基地！',
 'intelion07':'摧毁黑异魔王的中央控制系统！',
 'intelion08':'结束',
}
MAP_NAMES={
 '[2] cantia.spm':'[2] 坎提亚', '[2] eden goo.spm':'[2] 伊甸泥沼',
 '[3] brain break.spm':'[3] 脑力激荡', '[4] alien.spm':'[4] 异星',
 '[4] amoeba.spm':'[4] 变形虫', '[4] doughnut pan.spm':'[4] 甜甜圈',
 '[4] island fish.spm':'[4] 鱼形岛', '[4] new triangle.spm':'[4] 新三角',
 '[4] silent mobius.spm':'[4] 寂静莫比乌斯', '[6] Cyclops eye.spm':'[6] 巨人之眼',
 '[6] emblema.spm':'[6] 纹章', '[6] monster.spm':'[6] 怪兽',
 '[8] djinni.spm':'[8] 神灵', '[8] octopus.spm':'[8] 章鱼',
 '[8] twelve the heart.spm':'[8] 十二之心',
}
changes=[]; expected={}
def record(file,field,old,new):changes.append(dict(file=file,field=field,original=old,translation=new))
def replace_fixed(raw,start,size,text):
 # Only touch the occupied string and new terminator, retaining padding elsewhere.
 old=raw[start:start+size].split(b'\0')[0]
 assert len(old)<size
 new=text.encode('gbk');assert len(new)<size
 span=max(len(old),len(new))+1
 raw[start:start+span]=new+b'\0'*(span-len(new))
 return old

def main():
 assert not DEST.exists(), 'Output exists: do not overwrite an existing release'
 (ROOT/'校验记录').mkdir(exist_ok=True)
 source_pak=(SRC/'dev/atrox.pak').read_bytes();pak=Pak(source_pak)
 name='/atrox_pak/gamestr.rts';old=pak.read(name);text=old.decode('gbk');found=set()
 def main_sub(m):
  s=m[2]
  if s not in MAIN:return m[0]
  found.add(s);record(name,'主文本',s,MAIN[s]);return m[1]+MAIN[s]+m[3]
 # Operates on one line at a time; preserves the original malformed unrelated quote line.
 new=re.sub(r'(?m)^(\s*")([^"\r\n]*)(")',main_sub,text).encode('gbk')
 assert found==set(MAIN);assert len(new)<=len(old)
 new+=b' '*(len(old)-len(new));pak.write_same_size(name,new);expected[name]=new
 name='/atrox_pak/lf_help.t2b';old=pak.read(name);payload=swap_bits(old[88:]);text=payload.decode('cp949');found=set()
 def help_sub(m):
  orig=m[1];core=orig.strip()
  if core not in HELP:
   assert not re.search('[가-힣]',core)
   return m[0].encode('cp949')
  found.add(core);newcore=HELP[core]
  lead=orig[:len(orig)-len(orig.lstrip())].encode('ascii')
  translated=lead+newcore.encode('gbk');assert len(translated)<=len(orig.encode('cp949')),(core,newcore)
  translated+=b' '*(len(orig.encode('cp949'))-len(translated))
  record(name,'快捷键帮助',core,newcore)
  return b'"'+translated+b'"'
 parts=[];offset=0
 for m in re.finditer(r'"([^"\r\n]*)"',text):
  parts.append(text[offset:m.start()].encode('cp949'));parts.append(help_sub(m));offset=m.end()
 parts.append(text[offset:].encode('cp949'));newpayload=b''.join(parts)
 assert found==set(HELP);assert len(newpayload)==len(payload)
 # Same header, payload size, field widths, color codes, and reversible bit transform.
 new=old[:88]+swap_bits(newpayload);pak.write_same_size(name,new);expected[name]=new
 for name in pak.entries:
  if not name.endswith('.spm'):continue
  old=pak.read(name);raw=bytearray(old);stem=Path(name).stem
  m=re.fullmatch(r'(createse|hominian|intelion)(\d+)([ab]?)',stem);assert m
  race={'createse':'异魔族','hominian':'人类','intelion':'使徒族'}[m[1]]
  title=f'{race}战役 {m[2]}' + ('-'+m[3].upper() if m[3] else '')
  prior=replace_fixed(raw,62,32,title).decode('cp949');record(name,'战役标题',prior,title)
  prior=replace_fixed(raw,94,1024,DESCS[stem]).decode('cp949');record(name,'战役简介',prior,DESCS[stem])
  assert raw[:62]==old[:62] and raw[1118:]==old[1118:]
  new=bytes(raw);pak.write_same_size(name,new);expected[name]=new
 # Check all archive objects before making a delivery copy.
 check=Pak(pak.data);orig=Pak(source_pak)
 assert check.entries==orig.entries and len(check.entries)==1016
 for name in check.entries:
  assert check.read(name)==expected.get(name,orig.read(name)),name
 assert len(expected)==28
 shutil.copytree(SRC,DEST,copy_function=shutil.copy2)
 (DEST/'dev/atrox.pak').write_bytes(pak.data)
 for filename,title in MAP_NAMES.items():
  f=DEST/'maps'/filename;old=f.read_bytes();raw=bytearray(old)
  prev=replace_fixed(raw,62,32,title).decode('gbk',errors='replace')
  assert raw[:62]==old[:62] and raw[94:]==old[94:]
  f.write_bytes(raw);record('maps/'+filename,'对战地图标题',prev,title)
 instructions='''剩下的英文和韩文已经补好了。\r\n\r\n解压后打开 atrox.exe 就能玩。原来的游戏和存档先留着，别删。\r\n有文字显示不对的地方，截图发我就行。\r\n'''
 (DEST/'使用说明.txt').write_bytes(instructions.encode('utf-8-sig'))
 (ROOT/'校验记录/翻译对照.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2))
 manifest={}
 for f in sorted(DEST.rglob('*')):
  if f.is_file():manifest[str(f.relative_to(DEST))]={'size':f.stat().st_size,'sha256':sha(f.read_bytes())}
 (ROOT/'校验记录/交付文件清单.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 print(json.dumps({'output':str(DEST),'translation_fields':len(changes),'archive_files':len(pak.entries),'archive_objects_changed':len(expected),'external_maps':len(MAP_NAMES),'files':len(manifest)},ensure_ascii=False))
if __name__=='__main__':main()
