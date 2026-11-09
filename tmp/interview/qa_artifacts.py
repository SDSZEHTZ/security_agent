from pathlib import Path
from PIL import Image,ImageOps,ImageDraw
from pypdf import PdfReader
import pdfplumber, json, hashlib, zipfile, xml.etree.ElementTree as ET
root=Path('E:/security_agent');build=root/'tmp/interview'
files=sorted((build/'pdf_pages').glob('page-*.png'))
for first in range(0,len(files),6):
    canvas=Image.new('RGB',(3*565,2*815),'#dce4eb')
    for n,file in enumerate(files[first:first+6]):
        im=Image.open(file).convert('RGB');im.thumbnail((555,790))
        x=(n%3)*565+5;y=(n//3)*815+20
        canvas.paste(im,(x,y));ImageDraw.Draw(canvas).text((x+5,y-16),file.stem,fill='black')
    canvas.save(build/f'pdf-review-{first//6+1}.png')
pdf=next((root/'output/pdf').glob('*.pdf')); ppt=next((root/'output/presentation').glob('*.pptx'))
r=PdfReader(pdf);issues=[]
with pdfplumber.open(pdf) as d:
    for i,p in enumerate(d.pages):
        for c in p.chars:
            if c['x0']<40 or c['x1']>555 or c['top']<40 or c['bottom']>825:
                issues.append([i+1,c['text'],round(c['x0'],1),round(c['top'],1)])
chap=json.loads((build/'guide_content.json').read_text(encoding='utf-8'))
assert len(r.pages)==len(chap)+2
for i,item in enumerate(chap):
    extracted=r.pages[i+2].extract_text().replace(' ','').replace('\n','')
    assert item['title'].replace(' ','') in extracted,(i,item['title'])
ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
with zipfile.ZipFile(ppt) as z:
    note_names=[n for n in z.namelist() if n.startswith('ppt/notesSlides/notesSlide') and n.endswith('.xml')]
    assert len(note_names)==16
    for n in note_names:
        t=''.join(ET.fromstring(z.read(n)).itertext());assert '源码依据' in t,n
report={'pdf_pages':len(r.pages),'pdf_chapters':len(chap),'pdf_bookmarks':len(r.outline),'pdf_links_on_contents':len(r.pages[1].get('/Annots',[])),'pdf_geometry_issues':issues,'ppt_notes':len(note_names),'candidate_matches_final':hashlib.sha256((build/'candidate.pptx').read_bytes()).digest()==hashlib.sha256(ppt.read_bytes()).digest(),'files':[{ 'name':p.name,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in (ppt,pdf)]}
(build/'qa.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=True))
