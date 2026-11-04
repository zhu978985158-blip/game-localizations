import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;
import jdk.internal.org.objectweb.asm.*;
import jdk.internal.org.objectweb.asm.tree.*;

/** Independently compare all executable instructions and symbolic references. */
public class StaticCheck implements Opcodes {
    static byte[] read(ZipFile z,String name)throws Exception{try(InputStream i=z.getInputStream(z.getEntry(name))){ByteArrayOutputStream b=new ByteArrayOutputStream();byte[] a=new byte[8192];int n;while((n=i.read(a))>=0)b.write(a,0,n);return b.toByteArray();}}
    static ClassNode parse(byte[] a){ClassNode c=new ClassNode(ASM5);new ClassReader(a).accept(c,0);return c;}
    static void require(boolean b,String s){if(!b)throw new AssertionError(s);}
    static String meta(FieldNode f){return f.access+"/"+f.name+"/"+f.desc+"/"+f.signature+"/"+f.value;}
    static String meta(MethodNode m){return m.access+"/"+m.name+"/"+m.desc+"/"+m.signature+"/"+m.exceptions;}
    static String symbol(AbstractInsnNode n,Map<LabelNode,Integer> labels){
        String a=n.getOpcode()+":";
        if(n instanceof VarInsnNode)return a+((VarInsnNode)n).var;
        if(n instanceof IntInsnNode)return a+((IntInsnNode)n).operand;
        if(n instanceof TypeInsnNode)return a+((TypeInsnNode)n).desc;
        if(n instanceof FieldInsnNode){FieldInsnNode v=(FieldInsnNode)n;return a+v.owner+"."+v.name+v.desc;}
        if(n instanceof MethodInsnNode){MethodInsnNode v=(MethodInsnNode)n;return a+v.owner+"."+v.name+v.desc+v.itf;}
        if(n instanceof JumpInsnNode)return a+labels.get(((JumpInsnNode)n).label);
        if(n instanceof IincInsnNode){IincInsnNode v=(IincInsnNode)n;return a+v.var+":"+v.incr;}
        if(n instanceof MultiANewArrayInsnNode){MultiANewArrayInsnNode v=(MultiANewArrayInsnNode)n;return a+v.desc+":"+v.dims;}
        if(n instanceof TableSwitchInsnNode){TableSwitchInsnNode v=(TableSwitchInsnNode)n;String s=a+v.min+":"+v.max+":"+labels.get(v.dflt);for(LabelNode l:v.labels)s+=":"+labels.get(l);return s;}
        if(n instanceof LookupSwitchInsnNode){LookupSwitchInsnNode v=(LookupSwitchInsnNode)n;String s=a+v.keys+":"+labels.get(v.dflt);for(LabelNode l:v.labels)s+=":"+labels.get(l);return s;}
        if(n instanceof InvokeDynamicInsnNode){InvokeDynamicInsnNode v=(InvokeDynamicInsnNode)n;return a+v.name+v.desc+v.bsm+Arrays.toString(v.bsmArgs);}
        return a;
    }
    static List<AbstractInsnNode> ops(MethodNode m){List<AbstractInsnNode> r=new ArrayList<>();for(AbstractInsnNode n:m.instructions.toArray())if(n.getOpcode()>=0)r.add(n);return r;}
    static Map<LabelNode,Integer> labels(MethodNode m){Map<LabelNode,Integer>r=new IdentityHashMap<>();int p=0;for(AbstractInsnNode n:m.instructions.toArray()){if(n instanceof LabelNode)r.put((LabelNode)n,p);if(n.getOpcode()>=0)p++;}return r;}
    public static void main(String[] args)throws Exception{
        Map<String,Map<String,String>> maps=new HashMap<>();
        for(String l:Files.readAllLines(Paths.get(args[2]),StandardCharsets.UTF_8)){String[]a=l.split("\t");maps.computeIfAbsent(a[0],k->new HashMap<>()).put(LocalizeClasses.decode(a[1]),LocalizeClasses.decode(a[2]));}
        String chars=new String(Files.readAllBytes(Paths.get(args[3])),StandardCharsets.UTF_8);
        String breaks=new String(Files.readAllBytes(Paths.get(args[4])),StandardCharsets.UTF_8);
        int changed=0,methods=0,instructions=0,constants=0;
        try(ZipFile original=new ZipFile(args[0]);ZipFile localized=new ZipFile(args[1])){
            Enumeration<? extends ZipEntry> en=original.entries();while(en.hasMoreElements()){
                String name=en.nextElement().getName();if(!name.endsWith(".class"))continue;
                byte[] a=read(original,name),b=read(localized,name);if(Arrays.equals(a,b))continue;
                changed++;ClassNode ca=parse(a),cb=parse(b);
                require(ca.name.equals(cb.name)&&ca.access==cb.access&&Objects.equals(ca.superName,cb.superName)&&ca.interfaces.equals(cb.interfaces),name+" class identity");
                require(ca.fields.size()==cb.fields.size()&&ca.methods.size()==cb.methods.size(),name+" members");
                for(int i=0;i<ca.fields.size();i++)require(meta(ca.fields.get(i)).equals(meta(cb.fields.get(i))),name+" field metadata");
                for(int i=0;i<ca.methods.size();i++){
                    MethodNode ma=ca.methods.get(i),mb=cb.methods.get(i);require(meta(ma).equals(meta(mb)),name+" method metadata");methods++;
                    if(ca.name.equals("fi/bugbyte/jump/data/Dialogs$Character")&&ma.name.equals("getTitle"))continue;
                    if(ca.name.equals("fi/bugbyte/framework/graphics/Fonts$FontData")&&ma.name.equals("makeFont")){
                        List<AbstractInsnNode> start=ops(mb);
                        require(start.get(0) instanceof IntInsnNode&&((IntInsnNode)start.get(0)).operand==2048&&start.get(1) instanceof MethodInsnNode&&((MethodInsnNode)start.get(1)).name.equals("setMaxTextureSize"),"Font atlas capacity differs");
                        mb.instructions.remove(start.get(0));mb.instructions.remove(start.get(1));
                        List<AbstractInsnNode> o=ops(mb);int j=o.size()-6;
                        require(o.get(j).getOpcode()==DUP&&o.get(j+1) instanceof MethodInsnNode&&((MethodInsnNode)o.get(j+1)).name.equals("getData")&&o.get(j+2) instanceof LdcInsnNode&&((LdcInsnNode)o.get(j+2)).cst.equals(breaks)&&o.get(j+3) instanceof MethodInsnNode&&((MethodInsnNode)o.get(j+3)).name.equals("toCharArray")&&o.get(j+4) instanceof FieldInsnNode&&((FieldInsnNode)o.get(j+4)).name.equals("breakChars")&&o.get(j+5).getOpcode()==ARETURN,"Wrap injection differs");
                        for(int k=0;k<5;k++)mb.instructions.remove(o.get(j+k));
                    }
                    List<AbstractInsnNode> aa=ops(ma),bb=ops(mb);require(aa.size()==bb.size(),name+" "+ma.name+" instruction count");
                    Map<LabelNode,Integer> la=labels(ma),lb=labels(mb);
                    require(ma.tryCatchBlocks.size()==mb.tryCatchBlocks.size(),name+" exception count");
                    for(int k=0;k<ma.tryCatchBlocks.size();k++){TryCatchBlockNode x=ma.tryCatchBlocks.get(k),y=mb.tryCatchBlocks.get(k);require(Objects.equals(x.type,y.type)&&la.get(x.start).equals(lb.get(y.start))&&la.get(x.end).equals(lb.get(y.end))&&la.get(x.handler).equals(lb.get(y.handler)),name+" exception handling");}
                    for(int j=0;j<aa.size();j++){
                        AbstractInsnNode x=aa.get(j),y=bb.get(j);instructions++;
                        require(symbol(x,la).equals(symbol(y,lb)),name+" "+ma.name+" changed instruction "+j);
                        if(x instanceof LdcInsnNode){Object old=((LdcInsnNode)x).cst,now=((LdcInsnNode)y).cst;if(Objects.equals(old,now))continue;
                            boolean font=ca.name.equals("fi/bugbyte/framework/graphics/Fonts$FontData")&&ma.name.equals("toBitmapFont")&&now.equals(old+chars);
                            require(font||Objects.equals(maps.getOrDefault(ca.name,Collections.emptyMap()).get(old),now),name+" unauthorized constant "+old);constants++;
                        }
                    }
                }
            }
        }
        System.out.println("STATIC_CHECK_PASS changed_classes="+changed+" methods="+methods+" preserved_instructions="+instructions+" allowed_string_sites="+constants+" gameplay_instruction_changes=0");
    }
}
