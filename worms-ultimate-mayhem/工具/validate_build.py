from pathlib import Path
import json,re,struct,hashlib
from xom_language import Language,read_varint
ROOT=Path(__file__).resolve().parents[1]
TOKEN=r'/\*.*?\*/|%(?:\d+\$)?[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[hlL]*[diuoxXfFeEgGaAcspn%]'

def font_data(b):
    starts=[m.start() for m in re.finditer(b'CTNR',b)];assert len(starts)==103
    ends=starts[1:]+[len(b)];blocks=[b[a:z] for a,z in zip(starts,ends)]
    s=b.index(b'STRS');n,size=struct.unpack_from('<II',b,s+4);pos=s+12+n*4+size
    _,pos=read_varint(b,pos);pos+=2;_,pos=read_varint(b,pos);n=struct.unpack_from('<I',b,pos)[0];pos+=4
    desc=[struct.unpack_from('<3H',b,pos+6*i) for i in range(n)]
    pages={}
    for i in range(3,34):
        pos=7;tex,pos=read_varint(blocks[i],pos);values={}
        for name,fmt in [('chars','H'),('coords','2f'),('sizes','2f'),('bearings','2f'),('advances','f')]:
            n,pos=read_varint(blocks[i],pos);step=struct.calcsize('<'+fmt)
            values[name]=[struct.unpack_from('<'+fmt,blocks[i],pos+j*step) for j in range(n)];pos+=step*n
        assert len({len(v) for v in values.values()})==1
        assert len(blocks[i])-pos==6
        pages[i+3]={'texture':tex,**values}
    pos=7;ft={}
    for name,fmt in [('attributes',None),('pages',None),('ascii','H'),('map','H')]:
        n,pos=read_varint(blocks[34],pos)
        if fmt:arr=list(struct.unpack_from('<'+fmt*n,blocks[34],pos));pos+=2*n
        else:
            arr=[]
            for _ in range(n):v,pos=read_varint(blocks[34],pos);arr.append(v)
        ft[name]=arr
    ft['scale']=struct.unpack_from('<2f',blocks[34],pos)
    for index,packed,code in desc:
        assert ft['map'][index]==packed
        assert pages[ft['pages'][packed>>8]]['chars'][packed&255][0]==code
    return desc,pages,ft,blocks

def image_data(block):
    pos=7;_,pos=read_varint(block,pos);w,h,mips,flags=struct.unpack_from('<4H',block,pos);pos+=8
    arrays=[]
    for _ in range(2):
        n,pos=read_varint(block,pos);arrays.append(struct.unpack_from('<'+'I'*n,block,pos));pos+=4*n
    fmt=struct.unpack_from('<I',block,pos)[0];pos+=4;n,pos=read_varint(block,pos)
    assert n==sum(max(1,w>>i)*max(1,h>>i)*4 for i in range(mips))
    assert arrays[0]==tuple(max(1,w>>i)*4 for i in range(mips))
    off=0
    for i in range(mips):
        assert arrays[1][i]==off;off+=max(1,w>>i)*max(1,h>>i)*4
    assert block[pos+n:]==b'\0' and fmt==1
    return w,h,block[pos:pos+w*h*4]

def main():
    tr=json.loads((ROOT/'译文/主语言表.json').read_text());translated=0;errors=[]
    for name,items in tr.items():
        old=Language((ROOT/'原始解包/Worms Ultimate Mayhem/Game/Data/Language/PC'/name).read_bytes())
        new=Language((ROOT/'开发测试补丁/Game/Data/Language/PC'/name).read_bytes())
        source=dict(old.items());assert new.items()==[(k,items.get(k,v)) for k,v in old.items()]
        for k,v in items.items():
            assert re.findall(TOKEN,source[k])==re.findall(TOKEN,v),(name,k,'format tokens')
            assert '蠕虫' not in v and v.strip(),(name,k,'term or blank')
            translated+=1
    file='Game/Data/Bundles/Bundl03.xom'
    oldb=(ROOT/'原始解包/Worms Ultimate Mayhem'/file).read_bytes();newb=(ROOT/'开发测试补丁'/file).read_bytes()
    od,op,of,ob=font_data(oldb);nd,np,nf,nb=font_data(newb)
    assert oldb[:64]==newb[:64]
    assert nf['attributes']==of['attributes'] and nf['pages']==of['pages']
    assert nf['scale']==tuple(x*2 for x in of['scale'])
    old_desc=set(od);assert old_desc.issubset(set(nd))
    for i in list(range(3))+list(range(35,41))+list(range(72,103)):
        assert ob[i]==nb[i],('nonfont changed',i)
    for i in range(41,72):
        ow,oh,raw=image_data(ob[i]);nw,nh,newraw=image_data(nb[i]);assert (nw,nh)==(ow*2,oh*2)
        for y in range(oh):assert raw[y*ow*4:(y+1)*ow*4]==newraw[y*nw*4:y*nw*4+ow*4],('old atlas changed',i,y)
    available={chr(x[2]) for x in nd};needed={c for t in tr.values() for v in t.values() for c in v if ord(c)>127}
    missing=sorted(needed-available);assert not missing,missing
    result={'translated_records':translated,'language_reparse_verified':True,'control_tokens_preserved':True,'worm_term_check':True,
        'font_descriptor_count':len(nd),'font_mapping_verified':True,'original_character_mappings_retained':True,'original_texture_pixels_retained':True,'nonfont_objects_byte_identical':True,
        'missing_characters':missing,'windows_runtime_verified':False,'font_visual_game_verified':False,'output_font_sha256':hashlib.sha256(newb).hexdigest()}
    (ROOT/'验证/开发构建验收.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
