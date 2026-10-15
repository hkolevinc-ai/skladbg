"""Read Temu's metadata; change only the Template sheet's data rows in OOXML.

No Excel application is needed. All other ZIP members, reserved header rows,
dropdowns, validation rules, hidden metadata, and category-name formulas survive.
"""
from __future__ import annotations
import copy,io,pathlib,posixpath,re,zipfile,xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
def colnum(ref):
 n=0
 for c in re.match(r'[A-Z]+',ref)[0]:n=n*26+ord(c)-64
 return n
def colname(n):
 out=''
 while n:n,r=divmod(n-1,26);out=chr(65+r)+out
 return out
def rows(xml,strings):
 for _,elem in ET.iterparse(io.BytesIO(xml),events=('end',)):
  if elem.tag!='{'+NS['s']+'}row':continue
  row={}
  for c in elem.findall('s:c',NS):
   v=c.find('s:v',NS);value=v.text if v is not None else None
   if c.get('t')=='s' and value is not None:value=strings[int(value)]
   elif c.get('t')=='inlineStr':value=''.join(c.itertext())
   if value is not None:row[colnum(c.get('r'))]=value
  yield int(elem.get('r')),row
  elem.clear()

class TemuTemplate:
 def __init__(self,path):
  self.path=pathlib.Path(path);self.z=zipfile.ZipFile(self.path)
  self.strings=[]
  if 'xl/sharedStrings.xml' in self.z.namelist():
   root=ET.fromstring(self.z.read('xl/sharedStrings.xml'))
   self.strings=[''.join(e.itertext()) for e in root]
  rels=ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels'))
  targets={e.get('Id'):posixpath.normpath('xl/'+e.get('Target')) if not e.get('Target').startswith('/') else e.get('Target').lstrip('/') for e in rels}
  wb=ET.fromstring(self.z.read('xl/workbook.xml'))
  self.sheets={e.get('name'):targets[e.get('{'+NS['r']+'}id')] for e in wb.find('s:sheets',NS)}
  self.template_xml=self.z.read(self.sheets['Template']).decode('utf-8')
  self.headers={};self.keys={}
  for rn,r in rows(self.z.read(self.sheets['Template']),self.strings):
   if rn==2:self.headers=r
   if rn==4:self.keys=r;break
  self.by_name={}
  for col,name in self.headers.items():self.by_name.setdefault(name,[]).append(col)
  self.categories={int(r[1]):r[2] for _,r in rows(self.z.read(self.sheets['Category Name']),self.strings) if 1 in r and 2 in r}
  self.dropdowns={r[1]:[r[i] for i in sorted(r) if i>=3] for _,r in rows(self.z.read(self.sheets['Dropdown Lists']),self.strings) if 1 in r}
  self.required={};self.disabled={};self.conditional={}
  for _,r in rows(self.z.read(self.sheets['GoodsLevelMode']),self.strings):
   label=r.get(1,'');m=re.fullmatch(r'(\d+)_(require|disabled|condition_require)',label)
   if not m:continue
   target={'require':self.required,'disabled':self.disabled,'condition_require':self.conditional}[m[2]]
   target[int(m[1])]={k for k,v in r.items() if k!=1 and v}
  self.condition_rules={r[1]:[r[i] for i in sorted(r) if i>=3] for _,r in rows(self.z.read(self.sheets['Conditions List']),self.strings) if 1 in r}
  self.style={};self.category_formula=None
  first5=re.search(r'<row\b[^>]*\br="5"[^>]*>.*?</row>',self.template_xml,re.S)
  if first5:
   root=ET.fromstring('<root xmlns="'+NS['s']+'">'+first5[0]+'</root>')
   for c in root[0]:
    col=colnum(c.get('r'));self.style[col]=c.get('s')
    if col==self.column('Category Name'):
     f=c.find('s:f',NS);self.category_formula=f.text if f is not None else None
  self.capacity=4996

 def column(self,name):
  cols=self.by_name.get(name,[])
  return cols[0] if cols else None
 def columns(self,name):return self.by_name.get(name,[])
 def allowed(self,cat):return set(self.headers)-self.disabled.get(int(cat),set())
 def active_conditional(self,cat,values):
  active=set()
  for col in self.conditional.get(cat,set()):
   key=self.keys[col];triggers=self.condition_rules.get(key,[])
   if '|' in key:
    parent=key.split('|',1)[1].split(':')[-1]
    parents=[c for c,k in self.keys.items() if k.split('|')[0].startswith('t_3_Property:'+parent) and re.match(r'^t_3_Property:'+re.escape(parent)+r'(?:$|:)',k.split('|')[0])]
   elif key.startswith('t_3_Property:') and ':' in key.split('Property:',1)[1]:
    parents=[c for c,h in self.headers.items() if h=='6958 - Material Type']
   elif key=='t_8_Province of Origin':parents=self.columns('Country/Region of Origin')
   else:parents=[]
   if not triggers:
    # Some textile children have a parent ID but no trigger list in the supplied
    # file. Fill applicable fabric details conservatively, without introducing
    # silk/feather claims for a polyester/cotton product.
    selected=[self.headers[c].split(':',1)[-1] for c in parents if values.get(c) not in (None,'',0,'0')]
    header=self.headers[col]
    if 'Silk Ingredient' in header or 'Fabric Count' in header:selected=[v for v in selected if v=='Silk']
    elif 'Feather Type' in header:selected=[v for v in selected if re.search(r'Feather|Down',v,re.I)]
    elif header.endswith(' - Count'):selected=[v for v in selected if v=='Cotton']
    if selected and re.search(r'Square Weight|Count|Silk Ingredient|Feather Type',header):active.add(col)
    continue
   if any(str(values.get(c,'')) in triggers for c in parents):active.add(col)
  return active
 def choices(self,cat,col):
  name=self.headers.get(col,'');key=self.keys.get(col,'');stage=key.split('_')[1] if '_' in key else ''
  for lookup in [f't_{stage}_{cat}_{name}',f't_{stage}_{name}']:
   if lookup in self.dropdowns:return self.dropdowns[lookup]
  return []
 def pick(self,cat,col,value):
  options=self.choices(cat,col)
  if not options:return value
  folded=str(value).casefold()
  return next((v for v in options if str(v).casefold()==folded),None)
 def schema_report(self):
  return {'categories':self.categories,'columns':self.headers,'global_choices':{k:v for k,v in self.dropdowns.items() if k in ['t_1_Brand','t_7_Shipping Template']},'manufacturer_choices':sorted({x for k,v in self.dropdowns.items() if k.endswith('_Manufacturer') for x in v}),'eu_responsible_choices':sorted({x for k,v in self.dropdowns.items() if k.endswith('_EU Responsible person') for x in v})}
 def write(self,path,records):
  if len(records)>self.capacity:raise ValueError('Split output into at most 4996 data rows per workbook')
  xml=self.template_xml
  match=re.search(r'<sheetData(?:\s[^>]*)?>(.*?)</sheetData>',xml,re.S)
  if not match:raise ValueError('Template sheetData not found')
  data=match[1]
  reserved=''.join(m[0] for m in re.finditer(r'<row\b[^>]*\br="[1-4]"[^>]*>.*?</row>',data,re.S))
  if len(re.findall(r'<row\b',reserved))!=4:raise ValueError('Missing reserved Temu header rows')
  chunks=[reserved]
  category_col=self.column('Category Name')
  for rn,record in enumerate(records,5):
   values=dict(record);cat=int(values[self.column('Category')]);values[category_col]=self.categories[cat]
   cells=[]
   for col,value in sorted(values.items()):
    if value is None or value=='':continue
    ref=colname(col)+str(rn);style=f' s="{self.style[col]}"' if self.style.get(col) else ''
    if col==category_col and self.category_formula:
     cells.append(f'<c r="{ref}"{style} t="str"><f>{escape(self.category_formula)}</f><v>{escape(str(value))}</v></c>')
    elif isinstance(value,(int,float)):
     cells.append(f'<c r="{ref}"{style}><v>{value}</v></c>')
    else:
     text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',str(value))
     cells.append(f'<c r="{ref}"{style} t="inlineStr"><is><t xml:space="preserve">{escape(text)}</t></is></c>')
   chunks.append(f'<row r="{rn}">'+''.join(cells)+'</row>')
  xml=xml[:match.start(1)]+''.join(chunks)+xml[match.end(1):]
  last=max(4,len(records)+4);lastcol=colname(max(self.headers))
  xml=re.sub(r'<dimension\b[^>]*/>',f'<dimension ref="A1:{lastcol}{last}"/>',xml,count=1)
  path=pathlib.Path(path);path.parent.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as out:
   for info in self.z.infolist():out.writestr(copy.copy(info),xml.encode() if info.filename==self.sheets['Template'] else self.z.read(info.filename))
  return path
