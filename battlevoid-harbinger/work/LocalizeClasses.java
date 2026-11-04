import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.zip.*;
import jdk.internal.org.objectweb.asm.*;
import jdk.internal.org.objectweb.asm.tree.*;

/** Change display constants only; retain enum identities, fields and method signatures. */
public class LocalizeClasses implements Opcodes {
    static String decode(String s) { return new String(Base64.getDecoder().decode(s), StandardCharsets.UTF_8); }
    static AbstractInsnNode realNext(AbstractInsnNode n) {
        do { n=n.getNext(); } while(n!=null && n.getOpcode()<0); return n;
    }
    static AbstractInsnNode realPrev(AbstractInsnNode n) {
        do { n=n.getPrevious(); } while(n!=null && n.getOpcode()<0); return n;
    }
    static boolean enumIdentity(ClassNode c, MethodNode m, AbstractInsnNode n) {
        if((c.access & ACC_ENUM)==0 || !m.name.equals("<clinit>")) return false;
        AbstractInsnNode p=realPrev(n), q=realNext(n);
        return p!=null && p.getOpcode()==DUP && q!=null &&
            ((q.getOpcode()>=ICONST_M1 && q.getOpcode()<=ICONST_5) || q.getOpcode()==BIPUSH || q.getOpcode()==SIPUSH);
    }
    static void titleMethod(ClassNode c, List<String[]> titles) {
        List<String> enumNames=new ArrayList<>();
        for(FieldNode f:c.fields) if((f.access & ACC_ENUM)!=0) enumNames.add(f.name);
        if(enumNames.size()!=titles.size()) throw new IllegalStateException("Title count mismatch");
        for(int i=0;i<titles.size();i++) if(!enumNames.get(i).equals(titles.get(i)[0])) throw new IllegalStateException("Enum order changed");
        for(MethodNode m:c.methods) if(m.name.equals("getTitle") && m.desc.equals("()Ljava/lang/String;")) {
            m.instructions.clear(); m.tryCatchBlocks.clear();
            if(m.localVariables!=null) m.localVariables.clear();
            InsnList x=m.instructions;
            x.add(new IntInsnNode(BIPUSH,titles.size()));
            x.add(new TypeInsnNode(ANEWARRAY,"java/lang/String"));
            for(int i=0;i<titles.size();i++) {
                x.add(new InsnNode(DUP)); x.add(new IntInsnNode(BIPUSH,i));
                x.add(new LdcInsnNode(titles.get(i)[1])); x.add(new InsnNode(AASTORE));
            }
            x.add(new VarInsnNode(ALOAD,0));
            x.add(new MethodInsnNode(INVOKEVIRTUAL,c.name,"ordinal","()I",false));
            x.add(new InsnNode(AALOAD)); x.add(new InsnNode(ARETURN));
            m.maxStack=4; m.maxLocals=1;
            return;
        }
        throw new IllegalStateException("Missing getTitle");
    }
    public static void main(String[] args) throws Exception {
        Map<String,Map<String,String>> maps=new LinkedHashMap<>();
        Map<String,Integer> hits=new TreeMap<>();
        for(String line:Files.readAllLines(Paths.get(args[2]),StandardCharsets.UTF_8)) {
            String[] a=line.split("\t",-1); if(a.length!=3) throw new IllegalArgumentException(line);
            maps.computeIfAbsent(a[0],k->new LinkedHashMap<>()).put(decode(a[1]),decode(a[2]));
            hits.put(a[0]+"\t"+a[1],0);
        }
        String extra=new String(Files.readAllBytes(Paths.get(args[3])),StandardCharsets.UTF_8);
        List<String[]> titles=new ArrayList<>();
        for(String line:Files.readAllLines(Paths.get(args[4]),StandardCharsets.UTF_8)) titles.add(line.split("\t",-1));
        String breaks=new String(Files.readAllBytes(Paths.get(args[5])),StandardCharsets.UTF_8);
        String fontClass="fi/bugbyte/framework/graphics/Fonts$FontData";
        String titleClass="fi/bugbyte/jump/data/Dialogs$Character";
        Set<String> targets=new LinkedHashSet<>(maps.keySet()); targets.add(fontClass); targets.add(titleClass);
        int literalChanges=0,modifiedClasses=0,fontSets=0,wrapChanges=0;
        List<String> changeLog=new ArrayList<>();
        try(ZipFile zip=new ZipFile(args[0])) {
            for(String name:targets) {
                ZipEntry entry=zip.getEntry(name+".class");
                if(entry==null) throw new IllegalStateException("Missing class "+name);
                byte[] bytes; try(InputStream in=zip.getInputStream(entry)) { ByteArrayOutputStream o=new ByteArrayOutputStream();byte[] b=new byte[8192];int n;while((n=in.read(b))>=0)o.write(b,0,n);bytes=o.toByteArray(); }
                ClassReader reader=new ClassReader(bytes); ClassNode c=new ClassNode(ASM5); reader.accept(c,0);
                Map<String,String> map=maps.getOrDefault(name,Collections.emptyMap());
                for(MethodNode m:c.methods) {
                    if(name.equals(fontClass) && m.name.equals("makeFont")) {
                        InsnList capacity=new InsnList();
                        capacity.add(new IntInsnNode(SIPUSH,2048));
                        capacity.add(new MethodInsnNode(INVOKESTATIC,"com/badlogic/gdx/graphics/g2d/freetype/FreeTypeFontGenerator","setMaxTextureSize","(I)V",false));
                        m.instructions.insert(capacity);
                    }
                    for(AbstractInsnNode ins:m.instructions.toArray()) {
                        if(ins instanceof LdcInsnNode && ((LdcInsnNode)ins).cst instanceof String) {
                            LdcInsnNode ldc=(LdcInsnNode)ins;String old=(String)ldc.cst;
                            if(map.containsKey(old) && !enumIdentity(c,m,ins)) {
                                ldc.cst=map.get(old);literalChanges++;
                                String key=name+"\t"+Base64.getEncoder().encodeToString(old.getBytes(StandardCharsets.UTF_8));
                                hits.put(key,hits.get(key)+1);
                                changeLog.add(name+"\t"+m.name+m.desc+"\t"+key.split("\t",2)[1]);
                            }
                            if(name.equals(fontClass) && m.name.equals("toBitmapFont") && old.length()>100 && old.contains("ABCDEFGHIJKLMNOPQRSTUVWXYZ")) {
                                ldc.cst=old+extra; fontSets++;
                            }
                        }
                        if(name.equals(fontClass) && m.name.equals("makeFont") && ins.getOpcode()==ARETURN) {
                            InsnList x=new InsnList(); x.add(new InsnNode(DUP));
                            x.add(new MethodInsnNode(INVOKEVIRTUAL,"com/badlogic/gdx/graphics/g2d/BitmapFont","getData","()Lcom/badlogic/gdx/graphics/g2d/BitmapFont$BitmapFontData;",false));
                            x.add(new LdcInsnNode(breaks));
                            x.add(new MethodInsnNode(INVOKEVIRTUAL,"java/lang/String","toCharArray","()[C",false));
                            x.add(new FieldInsnNode(PUTFIELD,"com/badlogic/gdx/graphics/g2d/BitmapFont$BitmapFontData","breakChars","[C"));
                            m.instructions.insertBefore(ins,x);wrapChanges++;
                        }
                    }
                }
                if(name.equals(titleClass)) titleMethod(c,titles);
                ClassWriter writer=new ClassWriter(reader,ClassWriter.COMPUTE_MAXS);c.accept(writer);
                Path out=Paths.get(args[1],name+".class");Files.createDirectories(out.getParent());Files.write(out,writer.toByteArray());modifiedClasses++;
            }
        }
        for(Map.Entry<String,Integer> e:hits.entrySet()) if(e.getValue()==0) throw new IllegalStateException("Unmatched translation: "+e.getKey());
        if(fontSets!=2 || wrapChanges!=1) throw new IllegalStateException("Font patch mismatch "+fontSets+"/"+wrapChanges);
        Files.write(Paths.get(args[1],"literal_changes.tsv"),changeLog,StandardCharsets.UTF_8);
        System.out.println("classes="+modifiedClasses+" literal_sites="+literalChanges+" distinct_mappings="+hits.size()+" titles="+titles.size()+" font_charsets="+fontSets+" cjk_wrap="+wrapChanges);
    }
}
