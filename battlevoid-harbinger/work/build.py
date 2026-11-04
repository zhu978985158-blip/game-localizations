#!/usr/bin/env python3
"""Reproducible localization build. The original directory is always read-only."""
import base64, collections, copy, csv, hashlib, json, os, pathlib, re, subprocess, zipfile
from xml.sax.saxutils import escape

WORK=pathlib.Path(__file__).resolve().parent
BASE=WORK.parent
SOURCE=BASE/'inputs'
JAVA=pathlib.Path(os.environ['JAVA_HOME'])/'bin'
EXPECTED='966d08f6d1e2f243bcbca6c6c5794677be372539496b391d53e32b50e43759d5'
src=SOURCE/'harbinger.jar'
assert hashlib.sha256(src.read_bytes()).hexdigest()==EXPECTED,'Unexpected source version'
baseline={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()}
rows=list(csv.DictReader((WORK/'主文本_简体中文.tsv').open(),delimiter='\t'))
assert len(rows)==589 and len({r['id'] for r in rows})==589
translations={r['id']:r['zh_CN'] for r in rows}
assert all(translations.values())
maps=json.loads((WORK/'程序文本_简体中文.json').read_text())
titles=json.loads((WORK/'角色称谓_简体中文.json').read_text())
with zipfile.ZipFile(src) as source_zip:
    language_chars=''.join(re.findall(r'>[^<>]*<',source_zip.read('library/texts').decode()))
all_zh=list(translations.values())+[v for m in maps.values() for v in m.values()]+list(titles.values())+['简体中文　（）！？，。；：、【】《》“”‘’…—·',language_chars]
extra=''.join(sorted({c for s in all_zh for c in s if ord(c)>127}))
# Break after Han characters and closing punctuation, preserving Latin words.
breaks=''.join(c for c in extra if '\u3400'<=c<='\u9fff' or c in '，。！？；：、）】》」』')
(WORK/'font_characters.txt').write_text(extra)
(WORK/'line_break_characters.txt').write_text(breaks)
b64=lambda s:base64.b64encode(s.encode()).decode()
(WORK/'patch_mappings.tsv').write_text(''.join(f'{c}\t{b64(k)}\t{b64(v)}\n' for c,m in maps.items() for k,v in m.items()))
(WORK/'character_titles.tsv').write_text(''.join(f'{k}\t{v}\n' for k,v in titles.items()))
classes=WORK/'build_classes';classes.mkdir(exist_ok=True)
patched=WORK/'patched_classes';patched.mkdir(exist_ok=True)
subprocess.run([str(JAVA/'javac'),'-XDignore.symbol.file','-encoding','UTF-8','-d',str(classes),str(WORK/'LocalizeClasses.java')],check=True)
subprocess.run([str(JAVA/'java'),'-cp',str(classes),'LocalizeClasses',str(src),str(patched),str(WORK/'patch_mappings.tsv'),str(WORK/'font_characters.txt'),str(WORK/'character_titles.tsv'),str(WORK/'line_break_characters.txt')],check=True)
replacement={str(p.relative_to(patched)):p.read_bytes() for p in patched.rglob('*.class')}
with zipfile.ZipFile(src) as zin:
    original_text=zin.read('library/texts').decode('utf-8')
    seen=[];english=[]
    record_re=re.compile(r'(<(?P<tag>[^\s<>/]+)\s+id="(?P<id>\d+)"[^>]*>)(?P<body>.*?)(</(?P=tag)>)',re.S)
    def convert(m):
        key=m['id'];assert key in translations,key
        body=m['body'];ens=re.findall(r'<EN>(.*?)</EN>',body,re.S);assert len(ens)==1,key
        source=ens[0];target=translations[key]
        # These strings are plain text; preserve any engine placeholders if added later.
        tokens=lambda s:collections.Counter(re.findall(r'%\d*\$?[sdf]|\{\d+(?::[^}]+)?\}|\[[A-Fa-f0-9]{6,8}\]',s))
        assert tokens(source)==tokens(target),(key,'placeholder mismatch')
        seen.append(key);english.append({'id':key,'key':m['tag'],'en':source,'zh_CN':target})
        body=re.sub(r'<EN>.*?</EN>',lambda _: '<EN>'+escape(target)+'</EN>',body,count=1,flags=re.S)
        return m[1]+body+m[5]
    result=record_re.sub(convert,original_text)
    assert len(seen)==589 and set(seen)==set(translations)
    replacement['library/texts']=result.encode('utf-8')
    replacement['strings.xml']=zin.read('strings.xml').replace(b'<en>English</en>','<en>简体中文</en>'.encode())
    font_xml=zin.read('library/fonts').decode()
    # One shared, licensed font also covers the original Latin and Cyrillic languages.
    font_xml,n=re.subn(r'p="[^"]+\.ttf"','p="NotoSansCJKsc-Regular.otf"',font_xml)
    assert n==22
    replacement['library/fonts']=font_xml.encode()
    added={'library/NotoSansCJKsc-Regular.otf':(WORK/'NotoSansCJKsc-Regular.otf').read_bytes(),
           'META-INF/ChineseFont-OFL.txt':(WORK/'OFL.txt').read_bytes()}
    out=BASE/'汉化版'/'harbinger.jar';out.parent.mkdir(parents=True,exist_ok=True);temp=out.with_suffix('.building.jar')
    with zipfile.ZipFile(temp,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zout:
        for item in zin.infolist():zout.writestr(copy.copy(item),replacement.get(item.filename,zin.read(item)))
        for name,data in added.items():zout.writestr(name,data)
    with zipfile.ZipFile(temp) as check:
        assert check.testzip() is None
        assert len(check.namelist())==len(set(check.namelist()))
        assert set(check.namelist())==set(zin.namelist())|set(added)
        changed=[n for n in zin.namelist() if check.read(n)!=zin.read(n)]
        assert set(changed)==set(replacement),set(changed)^set(replacement)
        # Other languages and all resource identifiers retain their original bytes.
        strip_en=lambda s:re.sub(r'<EN>.*?</EN>','<EN/>',s,flags=re.S)
        assert strip_en(result)==strip_en(original_text)
    temp.replace(out)
    (WORK/'双语校对表.json').write_text(json.dumps(english,ensure_ascii=False,indent=2))
    report={'source_sha256':EXPECTED,'localized_sha256':hashlib.sha256(out.read_bytes()).hexdigest(),
            'main_text_entries':589,'hardcoded_mappings':sum(map(len,maps.values())),
            'character_titles':len(titles),'added_characters':len(extra),'break_characters':len(breaks),
            'changed_entries':changed,'added_entries':list(added),'zip_crc_valid':True,
            'other_languages_unchanged':True,'source_hashes':baseline}
    (WORK/'构建校验.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
assert baseline=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCE.iterdir() if p.is_file()}
print(json.dumps({k:v for k,v in report.items() if k not in ['changed_entries','source_hashes']},ensure_ascii=False))
