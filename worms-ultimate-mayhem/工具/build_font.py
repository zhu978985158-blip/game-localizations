"""Build a font-only test bundle, retaining all original object IDs and nonfont bytes.
Atlas orientation and metrics require Windows visual acceptance; this is not a release builder.
"""
from pathlib import Path
from copy import deepcopy
import struct, json, re, hashlib
from PIL import Image, ImageFont, ImageDraw
from xom_language import read_varint, varint
ROOT=Path(__file__).resolve().parents[1]
FONT=ROOT/'工具/字体源/NotoSansCJKsc-Bold.otf'
SIZE=1024

def collection(fmt, items):
    return varint(len(items))+b''.join(struct.pack('<'+fmt,*(v if isinstance(v,(list,tuple)) else [v])) for v in items)

def read_image(block):
    pos=7;name,pos=read_varint(block,pos)
    w,h,mips,flags=struct.unpack_from('<4H',block,pos);pos+=8
    arrays=[]
    for _ in range(2):
        n,pos=read_varint(block,pos);arrays.append(struct.unpack_from('<'+'I'*n,block,pos));pos+=4*n
    fmt=struct.unpack_from('<I',block,pos)[0];pos+=4
    n,pos=read_varint(block,pos)
    assert (w,h,mips,fmt)==(512,512,10,1)
    assert n==sum(max(1,w>>i)*max(1,h>>i)*4 for i in range(mips))
    assert block[pos+n:]==b'\0'
    return Image.frombytes('RGBA',(w,h),block[pos:pos+w*h*4]),flags

def encode_image(im, flags):
    strides=[];offsets=[];chunks=[];offset=0
    level=im
    while True:
        strides.append(level.width*4);offsets.append(offset)
        data=level.tobytes();chunks.append(data);offset+=len(data)
        if level.width==level.height==1:break
        level=level.resize((max(1,level.width//2),max(1,level.height//2)),Image.Resampling.LANCZOS)
    return (b'CTNR\0\0\0'+varint(0)+struct.pack('<4H',im.width,im.height,len(chunks),flags)
        +collection('I',strides)+collection('I',offsets)+struct.pack('<I',1)+varint(offset)+b''.join(chunks)+b'\0')

def glyph_image(char,w,h):
    scale=3
    font=ImageFont.truetype(str(FONT),64*scale)
    box=font.getbbox(char);bw=box[2]-box[0];bh=box[3]-box[1]
    assert bw and bh,(char,box)
    mask=Image.new('L',(bw+8*scale,bh+8*scale))
    d=ImageDraw.Draw(mask);d.text((4*scale-box[0],4*scale-box[1]),char,font=font,fill=255)
    mask.thumbnail(((w-10)*scale,(h-10)*scale),Image.Resampling.LANCZOS)
    canvas=Image.new('RGBA',(w*scale,h*scale));x=(w*scale-mask.width)//2;y=(h*scale-mask.height)//2
    from PIL import ImageFilter
    outline=mask.filter(ImageFilter.MaxFilter(6*scale+1))
    canvas.paste((15,20,24,255),(x,y),outline)
    canvas.paste((245,248,249,255),(x,y),mask)
    return canvas.resize((w,h),Image.Resampling.LANCZOS)

def build():
    source=ROOT/'原始解包/Worms Ultimate Mayhem/Game/Data/Bundles/Bundl03.xom'
    b=source.read_bytes();starts=[m.start() for m in re.finditer(b'CTNR',b)]
    assert len(starts)==103
    ends=starts[1:]+[len(b)];blocks=[b[a:z] for a,z in zip(starts,ends)]
    info=json.loads((ROOT/'验证/字体页结构.json').read_text());pages=deepcopy(info['pages']);font=deepcopy(info['font'])
    desc=json.loads((ROOT/'验证/初步字体映射.json').read_text());entries=deepcopy(desc['entries'])
    tr=json.loads((ROOT/'译文/主语言表.json').read_text());needed={ord(c) for m in tr.values() for v in m.values() for c in v if ord(c)>127}
    existing={x[2] for x in entries};missing=sorted(needed-existing)
    slots=[(x,y) for y in range(0,960,80) for x in range(512,992,80)]+[(x,y) for y in range(512,992,80) for x in range(0,480,80)]
    assert len(slots)==108 # extra right half plus lower left quadrant
    page_pos={ref:i for i,ref in enumerate(font['pages'])}
    patches={};page_rows=[];new_entries=[];redraw_count=0;added=set()
    # Re-render existing Han glyphs with the same SC font, preserving the old mapping indices.
    for page in pages:
        page['jobs']=[i for i,c in enumerate(page['characters']) if 0x3400<=c[0]<=0x9fff]
    for code in missing:
        candidates=[p for p in pages if len(p['jobs'])<len(slots) and len(p['characters'])<256]
        assert candidates,'Font atlas capacity exceeded; increase atlas grid without losing old glyphs'
        page=min(candidates,key=lambda p:(len(p['jobs']),len(p['characters'])))
        local=len(page['characters']);page['characters'].append([code]);page['coords'].append([0,0]);page['sizes'].append([74/512,74/512]);page['bearings'].append([0.5,0.37]);page['advances'].append([1.08]);page['jobs'].append(local)
        packed=(page_pos[page['container_id']]<<8)|local
        index=len(font['character_map']);font['character_map'].append(packed);new_entries.append([index,packed,code]);added.add(code)
        if code<256:font['ascii_map'][code]=packed
    sample_tiles=[]
    for page in pages:
        ti=page['texture_ref']-3;tex=blocks[ti]
        # XOglTextureMap fields: blend uint32, color vec4, texture varint.
        image_ref,_=read_varint(tex,7+20);image_index=image_ref-3
        original,flags=read_image(blocks[image_index]);atlas=Image.new('RGBA',(SIZE,SIZE));atlas.paste(original,(0,0))
        old_count=len(info['pages'][pages.index(page)]['characters']) if False else len(page['characters'])
        for i in range(len(page['coords'])):
            page['coords'][i]=[v/2 for v in page['coords'][i]]
            page['sizes'][i]=[v/2 for v in page['sizes'][i]]
        for job,(x,y) in zip(page['jobs'],slots):
            c=chr(page['characters'][job][0]);w=round(page['sizes'][job][0]*SIZE);h=round(page['sizes'][job][1]*SIZE)
            assert w<=80 and h<=80,(c,w,h)
            glyph=glyph_image(c,w,h)
            atlas.paste(glyph.transpose(Image.Transpose.FLIP_TOP_BOTTOM),(x,y))
            page['coords'][job]=[x/SIZE,y/SIZE]
            redraw_count+=1
            if ord(c) in needed and len(sample_tiles)<80:sample_tiles.append((c,glyph))
        assert atlas.crop((0,0,512,512)).tobytes()==original.tobytes(),'Original atlas pixels changed'
        raw=(b'CTNR\0\0\0'+varint(page['texture_ref'])+collection('H',page['characters'])
            +collection('2f',page['coords'])+collection('2f',page['sizes'])+collection('2f',page['bearings'])
            +collection('f',page['advances'])+bytes.fromhex(page['tail_hex']))
        patches[page['container_id']-3]=raw;patches[image_index]=encode_image(atlas,flags)
        page_rows.append({'page_ref':page['container_id'],'image_ref':image_ref,'glyphs':len(page['characters']),'redrawn':len(page['jobs']),'old_pixels_preserved':True})
    tail=bytearray.fromhex(font['tail_hex']);sx,sy=struct.unpack_from('<2f',tail);struct.pack_into('<2f',tail,0,sx*2,sy*2)
    patches[34]=(b'CTNR\0\0\0'+varint(len(font['attributes']))+b''.join(varint(x) for x in font['attributes'])
        +varint(len(font['pages']))+b''.join(varint(x) for x in font['pages'])
        +collection('H',font['ascii_map'])+collection('H',font['character_map'])+tail)
    entries=sorted(entries+new_entries,key=lambda x:x[2])
    # Original STRS end = first descriptor start. Preserve graph bytes after descriptor.
    s=b.index(b'STRS');n,size=struct.unpack_from('<II',b,s+4);start=s+12+4*n+size
    pos=start;_,pos=read_varint(b,pos);pos+=2;_,pos=read_varint(b,pos)
    oldn=struct.unpack_from('<I',b,pos)[0];oldend=pos+4+oldn*6
    prefix=b[:pos]+struct.pack('<I',len(entries))+b''.join(struct.pack('<3H',*x) for x in entries)+b[oldend:starts[0]]
    out=prefix+b''.join(patches.get(i,block) for i,block in enumerate(blocks))
    target=ROOT/'开发测试补丁/Game/Data/Bundles/Bundl03.xom';target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(out)
    lookup={p['container_id']:p for p in pages}
    for index,packed,code in entries:
        assert font['character_map'][index]==packed
        assert lookup[font['pages'][packed>>8]]['characters'][packed&255][0]==code
    assert not needed-{x[2] for x in entries}
    sheet=Image.new('RGB',(800,((len(sample_tiles)+9)//10)*90),(43,65,78))
    for i,(_,im) in enumerate(sample_tiles):sheet.paste(im,((i%10)*80,(i//10)*90),im)
    sheet.save(ROOT/'验证/中文字库样张.png')
    result={'original_sha256':hashlib.sha256(b).hexdigest(),'output_sha256':hashlib.sha256(out).hexdigest(),
        'original_glyphs':oldn,'new_glyphs':len(added),'redrawn_glyphs':redraw_count,'total_glyphs':len(entries),
        'missing_for_current_translations':0,'object_count_unchanged':True,'nonfont_blocks_identical':all(i in patches or blocks[i] in out for i in range(len(blocks))),
        'pages':page_rows,'status':'EXPERIMENTAL: Windows glyph orientation, baseline, size and resource loading untested',
        'font_source':'https://github.com/notofonts/noto-cjk','font_license':'工具/字体源/LICENSE.txt'}
    (ROOT/'验证/中文字库构建.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print({k:v for k,v in result.items() if k!='pages'})

if __name__=='__main__':build()
