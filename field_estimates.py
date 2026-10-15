"""User-authorized estimates. Every estimated cell is recorded with its basis.

There is deliberately no 'pick the first dropdown value' fallback. Unsupported
mandatory properties fail validation, so a new template cannot silently invent
manufacturer identities, regulatory documents, certificates or unknown enums.
"""
import collections,math,re
from category_rules import normalize
from descriptions import text,clean_title

# Product dimensions (cm), individual gross weight (g), material candidates.
# These are editable category/type estimates, not measurements from photographs.
PROFILES=[
 ('Gift Wrap Boxes',[20,15,10],100,['Paper']),
 ('Christmas Trees', [90,45,45],1800,['PVC','Plastic']),
 ('Christmas Stockings',[35,25,1],100,['Polyester','Fabric']),
 ('Christmas Garlands',[200,10,10],200,['Plastic']),
 ('Christmas Ball Ornaments',[6,6,6],40,['Plastic']),
 ('Christmas',[15,10,5],180,['Plastic']),
 ('Artificial Plants',[25,15,15],250,['Plastic']),
 ('Artificial Flowers',[35,15,10],180,['Polyester','Plastic']),
 ('Towels',[70,140,0.5],450,['Cotton']),
 ('Cleaning Cloths',[30,30,0.2],60,['Polyester','Microfiber']),
 ('Pillow Covers',[45,45,0.2],130,['Polyester']),
 ('Pillowcases',[70,50,0.2],180,['Cotton','Polyester']),
 ('Sheet & Pillowcase Sets',[220,200,0.2],1400,['Cotton','Polyester']),
 ('Blankets',[200,150,1],1000,['Polyester']),
 ('Bedspreads',[220,200,1],1300,['Polyester']),
 ('Travel Pillows',[30,28,10],300,['Polyester']),
 ('Bed Pillows',[60,40,15],650,['Polyester']),
 ('Slipcovers',[45,45,5],300,['Polyester']),
 ('Tablecloths',[180,140,0.2],400,['Polyester']),
 ('Garment Covers',[100,60,1],150,['Polyester','Fabric']),
 ('Seat Covers',[60,45,5],500,['Polyester']),
 ('Soccer Balls',[22,22,22],450,['PU','PVC','Rubber']),
 ('Volleyballs',[21,21,21],300,['PU','PVC','Rubber']),
 ('Basketballs',[24,24,24],650,['Rubber','PU','Synthetic Rubber']),
 ('Tennis Rackets',[68,28,4],400,['Aluminum Alloy','Aluminum','Metal']),
 ('Hats',[28,24,12],120,['Polyester','Cotton']),
 ('Belts',[110,3.5,0.3],200,['PU']),
 ('Backpacks',[42,30,15],600,['Polyester','Oxford Cloth']),
 ('Suitcases',[55,35,23],2800,['ABS','Plastic']),
 ('Folding Chairs',[45,40,75],2500,['Metal','Steel']),
 ('Stools',[30,30,40],1000,['Plastic','Metal']),
 ('Shelf',[45,30,70],2500,['Metal','Plastic']),
 ('Utility Racks',[40,30,60],2000,['Metal','Steel']),
 ('Wastebaskets',[30,25,40],750,['Plastic']),
 ('Storage Boxes',[25,18,12],350,['Plastic']),
 ('Decorative Boxes',[20,15,10],400,['Wood','Plastic']),
 ('Bread Boxes',[35,25,18],700,['Plastic']),
 ('Food Container',[20,15,8],300,['Plastic']),
 ('Lunch Boxes',[20,15,8],300,['Plastic']),
 ('Bowls',[20,20,8],450,['Glass','Ceramic','Plastic']),
 ('Plates',[24,24,3],500,['Ceramic','Glass']),
 ('Dinnerware Sets',[25,25,10],1500,['Ceramic','Glass']),
 ('Glassware',[9,9,12],280,['Glass']),
 ('Serving Trays',[35,25,3],500,['Plastic','Metal']),
 ('Serving Boards',[30,20,2],600,['Wood','Bamboo']),
 ('Cutting Boards',[30,20,2],500,['Plastic','Wood']),
 ('Flatware',[20,4,2],100,['Stainless Steel','Metal']),
 ('Cooking Utensil',[30,8,3],150,['Stainless Steel','Plastic']),
 ('Colanders',[25,25,12],250,['Stainless Steel','Metal']),
 ('Cookware Accessories',[20,20,3],180,['Plastic','Stainless Steel']),
 ('Cookware',[25,25,12],850,['Aluminum','Stainless Steel','Metal']),
 ('Bakeware',[25,25,6],300,['Carbon Steel','Metal','Silicone']),
 ('Kettles',[22,20,20],600,['Stainless Steel','Metal']),
 ('Household Mops & Bucket',[45,30,30],1600,['Plastic','Metal']),
 ('Mops',[120,30,10],650,['Plastic','Metal']),
 ('Cleaning Brushes',[25,8,6],150,['Plastic']),
 ('Brooms',[30,20,6],200,['Plastic']),
 ('Sponges',[12,8,4],50,['Plastic','Polyurethane','Foam']),
 ('Picture Frames',[25,20,2],300,['Plastic','Wood']),
 ('Photo Albums',[25,20,5],450,['Paper','Plastic']),
 ('Knives',[25,5,2],180,['Stainless Steel','Metal']),
 ('Wrenches',[25,8,3],350,['Steel','Metal','Carbon Steel']),
 ('Screwdriver',[25,8,4],250,['Steel','Metal','Plastic']),
 ('Hammers',[30,12,4],650,['Steel','Metal']),
 ('Mallets',[30,12,6],650,['Rubber','Wood']),
 ('Scissors',[20,8,2],140,['Stainless Steel','Metal']),
 ('Combs',[20,5,2],80,['Plastic','ABS']),
 ('Padlocks',[7,5,2],180,['Metal','Steel']),
 ('Watering Cans',[30,20,25],350,['Plastic']),
 ('Hoses',[30,30,8],700,['PVC','Plastic']),
 ('Canteens',[25,10,10],300,['Aluminum','Plastic']),
]
def profile(category):
 for word,dims,weight,mats in PROFILES:
  if word.casefold() in category.casefold():return list(dims),weight,list(mats),word
 return [25,15,10],300,['Plastic','Metal'],'small household article'

def complete_required(product,cat,description,t,config,facts,values,estimates,override):
 source=normalize(text(product['name'])+' '+text(product.get('description','')))
 dims,gross,mats,basis=profile(t.categories[cat]);allowed=t.allowed(cat)
 if re.search(r'дръжк.*капак',source):dims,gross,basis=[6,4,3],60,'lid knob'
 source_dims=facts.get('dimensions')
 if source_dims and not source_dims['is_package']:
  nums=source_dims['values_cm'];dims[:len(nums)]=nums
 mats=list(facts.get('materials') or mats)
 if re.search(r'микрофибър',source):mats=['Polyester','Microfiber']
 if re.search(r'нетъкан',source):mats=['Polypropylene','Polyester','Fabric']
 if re.search(r'слама|сламен',source):mats=['Straw','Paper straw','Raffia Grass']
 if re.search(r'ангора',source):mats=['Rabbit Hair','Wool']
 if re.search(r'филц',source):mats=['Polyester','Felt']
 if re.search(r'полар',source):mats=['Polyester']
 def add(col,value,reason=None):
  if col not in allowed or value in (None,''):return False
  selected=t.pick(cat,col,value)
  if selected is None:return False
  values[col]=selected
  if reason:estimates.append({'column':col,'field':t.headers[col],'value':selected,'basis':reason,'status':'estimate'})
  return True
 def candidates(col,options,reason):
  for v in options:
   if add(col,v,reason):return True
  return False
 def put(name,value,reason=None):
  for col in t.columns(name):
   if col in allowed:return add(col,value,reason)
  return False
 def material_candidates(food=False):
  synonyms={'Glass':['Soda-lime Glass','Glass'],'Wood':['Log','Wood','Wooden'],'Plastic':['Polypropylene (PP)','Polypropylene(PP)','PP','Plastic'],
   'Stainless Steel':['Stainless Steel','Metal'],'Metal':['Metal','Steel','Stainless Steel','Iron'],
   'Ceramic':['Ceramics','Ceramic'],'Porcelain':['Ceramics','Porcelain','Ceramic'],
   'Nickel Silver':['Nickel Silver','Metal','Stainless Steel'],'Steel':['Steel','Carbon Steel','Metal'],
   'PVC':['Polyvinyl Chloride (PVC)','PVC','Polyvinyl chloride'],
   'Polyester':['Polyester','Polyester fiber','Polyester (polyester Fiber)','Chemical Fiber','Fabric','Other Textile Materials','PET (polyethylene Terephthalate)'],
   'Cotton':['Cotton','Cotton Blend','Other Textile Materials'],
   'Plastic':['Polypropylene (PP)','Polypropylene(PP)','PP (polypropylene)','PP','Plastic'],
   'Abs (acrylonitrile Butadiene Styrene)':['Acrylonitrile Butadiene Styrene (ABS)','ABS','Acrylonitrile Butadiene Styrene']}
  out=[]
  for m in mats:
   out.extend(synonyms.get(m,[m]) if food else [m]+synonyms.get(m,[]))
  return list(dict.fromkeys(out))
 # Resolve variation theme from actual template choices, including compound-only
 # categories. One row per source listing never invents unlisted child SKUs.
 options=t.choices(cat,t.column('Variation Theme'));required=t.required[cat]
 theme=values.get(t.column('Variation Theme'))
 wanted=[t.headers[c] for c in required if 1662<=c<=1670]
 compatible=[v for v in options if all(w in v.split(' × ') for w in wanted)]
 if not theme or (wanted and theme not in compatible):
  preferred=['Color × Size','Size','Size - Circumference In Inches','Items','Model','Color']
  theme=next((v for v in preferred if v in (compatible or options)),None)
  if theme is None and compatible:theme=min(compatible,key=lambda v:len(v.split(' × ')))
  if theme:put('Variation Theme',theme)
 if theme:
  for axis in theme.split(' × '):
   cols=[c for c in t.columns(axis) if c in allowed]
   if not cols:continue
   col=cols[-1] if axis=='Color' else cols[0]
   if values.get(col) not in (None,''):continue
   if axis=='Items':add(col,clean_title(product['name'])[:100])
   elif axis=='Model':add(col,str(product.get('sku') or product['id']))
   elif axis=='Color':candidates(col,[description.get('color')]+(['Multicolor'] if len(facts.get('colors',[]))>1 else facts.get('colors',[]))+['Multicolor','Black'],None if description.get('color') or facts.get('colors') else 'unspecified design/color; estimated assortment')
   elif axis.startswith('Size'):
    m=re.search(r'(?:№|номер|size)\s*(\d+)',source)
    v=override.get('size') or (m[1] if m else source_dims['label'] if source_dims else ' × '.join(f'{x:g}' for x in dims[:2])+' cm')
    if 'Circumference' in axis:v='29.5' if cat==36322 else '22.8'
    add(col,v,None if (source_dims or m) and 'Circumference' not in axis else 'nominal dimensions for '+basis)
   elif axis=='Style':add(col,clean_title(product['name'])[:100])
  if any(axis.startswith('Size') for axis in theme.split(' × ')):
   family='101 - Custom size';put('Size Family',family)
   subs=t.dropdowns.get(f't_4_{cat}_{family}_Sub-Size Family',[])
   if len(subs)==1:put('Sub-Size Family',subs[0])
 # Packaging has its own dimensions. Textiles are folded, long handles detached,
 # balls deflated; never substitute shipping sizes into product size charts.
 if config.get('estimate_missing_packages'):
  package=config.get('default_package_cm')
  if not package:
   if any(x in t.categories[cat] for x in ['Bedding','Towels','Tablecloth','Garment','Slipcover','Seat Cover']):package=[35,25,8]
   elif 'Balls' in t.categories[cat]:package=[25,20,8]
   elif 'Mops' in t.categories[cat]:package=[65,30,15]
   elif 'Christmas Garlands' in t.categories[cat]:package=[25,15,8]
   elif 'Christmas Trees' in t.categories[cat]:
    m=re.search(r'(\d+)\s*см',source);h=int(m[1]) if m else 90;package=[max(40,round(h*0.65)),25,25];gross=max(700,round(h*20))
   else:package=[round(x+3,1) for x in dims]
  count=facts.get('set_quantity',1)
  if count>1:package=[package[0],package[1],round(package[2]*min(count,4),1)]
  for name,v in zip(['Length - cm','Width - cm','Height - cm'],package):
   col=t.column(name)
   if values.get(col) in (None,''):add(col,float(v),'packaging estimate for '+basis+'; source dimensions where available')
  col=t.column('Weight - g')
  if values.get(col) in (None,''):
   w=config.get('default_package_weight_g') or (facts.get('weight_g') or gross)*count+50
   add(col,round(float(w),1),'gross packaging estimate; source mass + packaging allowance' if facts.get('weight_g') else 'gross packaging estimate for '+basis)
 def resolve(col):
  name=t.headers[col];reason='estimated characteristic for '+basis
  if name in {'Manufacturer','EU Responsible person'}:return
  if name=='Province of Origin':
   v=override.get('province_of_origin',config.get('province_of_origin'))
   result=add(col,v,'user-approved supplier information marker' if v=='Not provided by supplier' else None)
   if result and v=='Not provided by supplier':estimates[-1]['status']='supplier_information_missing'
   return result
  if name=='Individually packed':return add(col,'Yes','assumed one individually packed sellable listing')
  if name=='Unit':return candidates(col,['cm-g-ml','cm'],None)
  if ' - Product - ' in name:
   detail=name.split(' - Product - ')[1]
   v=dims[0] if detail=='Length' else dims[1] if detail=='Width' else dims[2] if detail=='Height' else max(100,gross-150) if detail=='Filling weight' else 3.5 if detail=='Strap width' else 110 if detail=='Strap length' else None
   if 'Pillowcase' in name:v=70 if detail=='Length' else 50
   if 'Fitted sheet' in name:v=200 if detail=='Length' else 160 if detail=='Width' else 25
   return add(col,v,None if source_dims and detail in {'Length','Width'} and 'Pillowcase' not in name and 'Fitted sheet' not in name else reason)
  if ':' in name and re.match(r'\d+ - ',name):return
  if name.endswith(' - Material Type'):
   textile=bool(re.search(r'Polyester|Cotton|Fabric|Linen|Wool|Microfiber',','.join(mats),re.I))
   return add(col,'Textile Material' if textile else 'Non-textile Material',reason)
  if name.endswith(' - Food Contact Material'):return candidates(col,material_candidates(True),'material subtype inferred from source/general product type')
  if re.search(r' - (Material|Major Material|Surface Material|Panel Material|Shell Material|Frame Material)$',name):return candidates(col,material_candidates(),None if facts.get('materials') and any(t.pick(cat,col,m) is not None for m in facts['materials']) else reason)
  if re.search(r'Handle|Comb Handle',name):
   preferred=['Stainless Steel','Metal'] if any(x in t.categories[cat] for x in ['Flatware','Spoons','Forks']) else ['Plastic','ABS Plastic','ABS','Wood','Wooden handle']
   roles=[(r'дървен[аои].*дръжк|дръжк.*(?:дървена|дърво)',['Wood','Wooden handle']),
    (r'пластмасов[аои].*дръжк|дръжк.*пластмас',['Plastic','ABS Plastic']),
    (r'бамбуков[аои].*дръжк|дръжк.*бамбук',['Bamboo','Wood','Wooden handle']),
    (r'дръжк.*неръждаем|неръждаем.*дръжк',['Stainless Steel','Metal']),
    (r'силиконов[аои].*дръжк|дръжк.*силикон',['Silicone'])]
   for pattern,options in roles:
    if re.search(pattern,source) and candidates(col,options,None):return True
   return candidates(col,preferred,reason)
  if name.endswith(' - Bristle Material'):return candidates(col,['Plastic','Nylon'],reason)
  if name.endswith(' - Blade Material'):return candidates(col,['Stainless Steel','Steel','Carbon Steel','Metal'],reason)
  if name.endswith(' - Buckle Material'):return candidates(col,['iron','Metal','Stainless Steel'],reason)
  if name.endswith(' - Liner Material'):return candidates(col,['Polyester','N/A'],reason)
  if name.endswith(' - Filling Material'):return candidates(col,['No filling','Polyester','Foam'],reason)
  if 'Square Gram Weight' in name:
   if name.endswith(' - unit'):return add(col,'g/㎡')
   weight=400 if 'Towels' in t.categories[cat] else 250 if 'Blankets' in t.categories[cat] else 120
   if not t.choices(cat,col):return add(col,weight,reason)
   return candidates(col,['120-130g','120-130 g/㎡','120-140 g/㎡','100-120 g/㎡','100-110 g/㎡','100-200 g/㎡','200-300 g/㎡','300-400 g/㎡'],reason)
  if name.endswith(' - Closure Type'):return candidates(col,['Zipper','Envelope','Other Closure Types','Latch','Flip top'],reason)
  if name.endswith(' - Power Supply'):
   power='USB Powered' if 'usb' in source else 'Dry Battery Power' if re.search(r'батери|светещ|светва|led|музикален|танцуващ',source) else 'Use Without Electricity'
   return candidates(col,[power]+(['Use without power'] if power=='Use Without Electricity' else []),reason if power!='Use Without Electricity' else None)
  if name.endswith(' - Power Mode'):return candidates(col,['USB' if 'usb' in source else 'Battery Powered' if re.search(r'батери|светещ|led',source) else 'Without electricity'],reason)
  if name.endswith(' - Battery Properties'):return candidates(col,['Non-rechargeable Battery' if re.search(r'батери|светещ|светва|led|музикален|танцуващ',source) else 'Without Battery'],reason)
  if name.endswith(' - Applicable Age Group'):return candidates(col,['14 Years+','18 Years+','12-14 Years Old'],reason+'; intended user age, not a tested safety rating')
  if name.endswith(' - Surface Finishing Type'):return candidates(col,['Polishing' if any(m in mats for m in ['Metal','Steel','Stainless Steel']) else 'Matte'],reason)
  if name.endswith(' - Applicable Models'):return candidates(col,['Universally Applicable','See Product Details'],reason)
  if name.endswith(' - Can Be Used For Food Contact'):return add(col,'Yes','intended use as a food utensil; not a food-safety certification')
  if name.endswith(' - Water Resistance Level'):return add(col,'Non-water resistant',reason)
  if name.endswith(' - Stainless Steel Grade'):return candidates(col,['201 Stainless Steel','201','Other'],reason+'; unverified grade')
  if name.endswith(' - Lip and Rim Contact'):return candidates(col,['Yes','No'],reason)
  if 'Operating Voltage' in name:return candidates(col,['≤36V','3V','5V','220V-240V'],reason)
  if 'Plug Type' in name:return candidates(col,['European Plug','EU Plug'],reason)
  if 'Thickness' in name:return add(col,'cm' if 'cm' in name else 'mm') if name.endswith(' - unit') else add(col,0.2 if 'cm' in name else 2,reason)
  if 'Battery Capacity' in name:return add(col,'mAh') if name.endswith(' - unit') else add(col,500,reason)
  if name.endswith(' - Count'):return candidates(col,['40 count','40','40S','40s','Below 60'],reason)
  if 'Fabric Count' in name:return candidates(col,['200','200TC','200 Thread Count','Below 300'],reason)
  if 'Fabric Square Weight' in name or 'Square Weight Of Lining Fabric' in name:return candidates(col,['120g','120-130g','100-200g','100-200 g/㎡','100-200 g/m²','100-150 g/㎡','Below 200g/㎡'],reason)
 def percent_groups(required_cols):
  groups=collections.defaultdict(list)
  for c in sorted(required_cols):
   if ':' in t.headers[c] and re.match(r'\d+ - ',t.headers[c]):groups[t.keys[c].split('Property:')[1].split(':')[0]].append(c)
  for _,cols in groups.items():
   # Alternative percentages share one property, and must total 100%, not 100%
   # in every material cell. Preserve genuine partial source percentages.
   existing={c:float(values[c]) for c in cols if values.get(c) not in (None,'')}
   total=sum(existing.values())
   if math.isclose(total,100):continue
   preferred=['Polyester'] if any('Filling Material:' in t.headers[c] or 'Liner Material:' in t.headers[c] for c in cols) else mats+['Polyester','Cotton']
   chosen=next((c for m in preferred for c in cols if t.headers[c].split(':',1)[1].casefold()==m.casefold() and c not in existing),None)
   if chosen is None and not existing:chosen=next((c for c in cols if t.headers[c].endswith(':Polyester')),None)
   if chosen is not None and 0<=total<100:add(chosen,round(100-total,3),'estimated fibre composition; percentage not verified by supplier')
 # Conditional requirements can cascade (food contact -> material subtype;
 # stainless steel -> grade). Iterate until the selected attributes stabilize.
 for _ in range(4):
  req=set(required)|t.active_conditional(cat,values)
  groups=collections.defaultdict(list)
  for c in sorted(req):groups[re.sub(r'(Property:\d+):.*$',r'\1',t.keys[c])].append(c)
  for cols in groups.values():
   if any(values.get(c) not in (None,'') for c in cols):continue
   for c in cols:
    resolve(c)
    if values.get(c) not in (None,''):break
  percent_groups(req)
