"""Extrai séries de linhas de um SVG matplotlib (SEEDS2 figures) e converte pixels -> dados pelos ticks."""
import re, sys, json
import xml.etree.ElementTree as ET
NS='{http://www.w3.org/2000/svg}'
def load(f):
    parser=ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
    return ET.parse(f,parser).getroot()
def comments(el):
    return [c.text.strip() for c in el.iter() if c.tag is ET.Comment]
def num(s):
    s=s.replace('−','-').replace('−','-')
    if re.fullmatch(r'-?\d+(\.\d+)?',s): return float(s)
    if re.fullmatch(r'-?\d{1,3}(,\d{3})+(\.\d+)?',s): return float(s.replace(',',''))
    return None
def path_pts(d):
    toks=re.findall(r'[MLz]|-?\d+(?:\.\d+)?(?:e-?\d+)?',d)
    segs=[];cur=[];i=0
    while i<len(toks):
        t=toks[i]
        if t=='M':
            if cur: segs.append(cur)
            cur=[(float(toks[i+1]),float(toks[i+2]))]; i+=3
        elif t=='L':
            cur.append((float(toks[i+1]),float(toks[i+2]))); i+=3
        elif t=='z': i+=1
        else: i+=1
    if cur: segs.append(cur)
    return segs
def run(f):
    root=load(f)
    fig=[g for g in root.iter(NS+'g') if g.get('id')=='figure_1'][0]
    axes=[g for g in fig if g.tag==NS+'g' and (g.get('id') or '').startswith('axes_')]
    res=[]
    xticks=[]
    for ax in axes:
        yt=[];
        for g in ax.iter(NS+'g'):
            gid=g.get('id') or ''
            if gid.startswith('ytick_'):
                use=[u for u in g.iter(NS+'use') if u.get('y')]
                cm=[num(c) for c in comments(g)]
                cm=[c for c in cm if c is not None]
                if use and cm: yt.append((float(use[0].get('y')),cm[0]))
            if gid.startswith('xtick_'):
                use=[u for u in g.iter(NS+'use') if u.get('x')]
                cm=comments(g)
                if use and cm: xticks.append((float(use[0].get('x')),' '.join(cm)))
        title=[c for c in comments(ax) if not re.fullmatch(r'[-−\d.,:/ ]+',c)]
        lines=[]
        for g in ax:
            if g.tag==NS+'g' and (g.get('id') or '').startswith('line2d_'):
                for p in g.iter(NS+'path'):
                    if p.get('clip-path') and p.get('d') and 'd5dae1' not in (p.get('style') or ''):
                        st=p.get('style'); col=re.search(r'stroke: (#[0-9a-f]{6})',st).group(1)
                        lines.append({'color':col,'dash':'dasharray' in st,'segs':path_pts(p.get('d'))})
                # markers (use) for lines+markers
                uses=[u for u in g.iter(NS+'use') if u.get('x') and g.get('clip-path') is None]
        # markers: <g clip-path=...><use x y>
        res.append({'yticks':yt,'title':title,'lines':lines,'ax':ax})
    return res,xticks
def ymap(yt):
    (p1,v1),(p2,v2)=yt[0],yt[-1]
    return lambda py: v1+(py-p1)*(v2-v1)/(p2-p1)
if __name__=='__main__':
    res,xt=run(sys.argv[1])
    print('xticks',xt[:8])
    for i,a in enumerate(res):
        print('AX',i,a['title'][:6],'yticks',a['yticks'])
        for l in a['lines']:
            print('   line',l['color'],l['dash'],'nsegs',len(l['segs']),'npts',sum(len(s) for s in l['segs']))
