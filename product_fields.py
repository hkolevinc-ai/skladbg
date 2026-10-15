import collections,html,re
from decimal import Decimal
from category_rules import normalize
from descriptions import clean_title,image_urls,text

MATERIALS=[(r'неръждаем|инокс|inox',['Stainless Steel']), (r'меламин',['Melamine']), (r'порцелан',['Porcelain','Ceramic','Ceramics']), (r'керами',['Ceramic','Ceramics']), (r'боросиликат',['Borosilicate Glass']), (r'стъкл',['Glass']), (r'бамбук',['Bamboo']), (r'дървен|дърво',['Wood']), (r'чугун',['Cast Iron']), (r'алумини',['Aluminum']), (r'алпака',['Nickel Silver','Metal']), (r'въглеродна стомана',['Steel','Metal']), (r'стомана',['Steel','Metal']), (r'метал',['Metal','Iron']), (r'силикон',['Silicone']), (r'пвц|\bpvc\b',['PVC','Polyvinyl Chloride','Plastic']), (r'пластмас',['Plastic']), (r'гума|гумен',['Rubber']), (r'поли[еэ]стер',['Polyester']), (r'памук|памуч',['Cotton']), (r'полипропилен',['Polypropylene(PP)','Polypropylene']), (r'\bабс\b|\babs\b',['Abs (acrylonitrile Butadiene Styrene)']), (r'емайл',['Enamel','enamel']), (r'харти|картон',['Paper']), (r'кожа|кожен',['Leather'])]
COLORS=[(r'черен|черна|черни','Black'),(r'бял|бяла|бели','White'),(r'червен|червена','Red'),(r'син(?: |я|и|$)','Blue'),(r'зелен','Green'),(r'жълт','Yellow'),(r'розов','Pink'),(r'сив','Grey'),(r'кафяв','Brown'),(r'лилав','Purple'),(r'оранж','Orange'),(r'бежов','Beige'),(r'злат','Gold'),(r'среб','Silver'),(r'прозрач','Transparent')]
DIMENSIONS=re.compile(r'(?<![\d.])(\d+(?:[.,]\d+)?)\s*[xх×*]\s*(\d+(?:[.,]\d+)?)(?:\s*[xх×*]\s*(\d+(?:[.,]\d+)?))?\s*(cm|cм|см|mm|мм|метра|метър|m|м)(?![a-zа-я])',re.I)
def extract_facts(product):
 name=text(product['name']);body=text(product.get('description','')+' '+product.get('short_description',''));source=name+' '+body;s=normalize(source)
 mats=[];names=[]
 for pattern,aliases in MATERIALS:
  if re.search(pattern,s):
   if aliases[0] not in names:names.append(aliases[0]);mats.extend(x for x in aliases if x not in mats)
 dims=None
 m=DIMENSIONS.search(name) or DIMENSIONS.search(body)
 if m:
  factor=0.1 if m[4].lower() in {'mm','мм'} else 100 if m[4].lower() in {'м','m','метра','метър'} else 1
  numbers=[float(x.replace(',','.'))*factor for x in m.groups()[:3] if x]
  dims={'values_cm':numbers,'label':' × '.join(f'{x:g}' for x in numbers)+' см','source':'source_title_or_description','is_package':bool(re.search(r'опаков|пакет',name,re.I))}
 weight=None
 m=re.search(r'(?<![\d.])(\d+(?:[.,]\d+)?)\s*(кг|kg|гр\.?|gram|грама|г)(?![a-zа-я])',s)
 if m:weight=float(m[1].replace(',','.'))*(1000 if m[2] in {'kg','кг'} else 1)
 capacity=None;m=re.search(r'(?<![\d.])(\d+(?:[.,]\d+)?)\s*(мл|ml|литра|литър|литри|л\b)',s)
 if m:capacity=m[1]+' '+m[2]
 count=1
 # "12 in a display/carton" is wholesale ordering, not proof of the sellable set.
 m=re.search(r'(?:комплект|комлект|сет)\s*(?:от\s*)?(\d+)\s*(?:броя|бр\.?|части|чифта)|(?:\b(\d+)\s*(?:броя|бр\.?|части))\s*(?:в\s*)?(?:комплект|к-кт|к-т)',s)
 if m:count=int(m[1] or m[2])
 else:
  m=re.search(r'(?:комплект|комлект|сет)\s+от\s+(\d+)\b',s)
  if m:count=int(m[1])
 colors=list(dict.fromkeys(color for pattern,color in COLORS if re.search(pattern,s)))
 return {'materials':mats,'material_names':names,'dimensions':dims,'weight_g':weight,'capacity':capacity,'set_quantity':count,'colors':colors}
def choose(options,candidates):
 for candidate in candidates:
  hit=next((v for v in options if str(v).casefold()==str(candidate).casefold()),None)
  if hit is not None:return hit
 return None
def property_group(key):
 # Repeated material cells and material-percentage columns are alternative inputs.
 return re.sub(r'(Property:\d+):.*$',r'\1',key)
EXEMPT_REQUIRED={'Manufacturer','EU Responsible person'}
def required_missing(template,cat,values):
 groups=collections.defaultdict(list)
 for col in template.required.get(cat,set())|template.active_conditional(cat,values):
  if template.headers[col] not in EXEMPT_REQUIRED:groups[property_group(template.keys[col])].append(col)
 return [template.headers[cols[0]].split(':')[0] for cols in groups.values() if not any(values.get(c) not in (None,'') for c in cols)]
def validate_record(template,cat,values):
 errors=['missing_required:'+name for name in required_missing(template,cat,values)]
 percent_groups=collections.defaultdict(list)
 for col,value in values.items():
  if col not in template.allowed(cat):errors.append('disabled_column:'+str(col))
  if template.pick(cat,col,value) is None:errors.append('invalid_final_dropdown:'+template.headers[col])
  if re.match(r'\d+ - [^:]+:',template.headers[col]):percent_groups[property_group(template.keys[col])].append(col)
 for group,cols in percent_groups.items():
  try:
   nums=[float(values[c]) for c in cols]
   if any(n<0 or n>100 for n in nums) or abs(sum(nums)-100)>0.01:errors.append('invalid_percentage_total:'+group)
  except (ValueError,TypeError):errors.append('invalid_percentage:'+group)
 theme=values.get(template.column('Variation Theme'),'')
 for axis in theme.split(' × '):
  cols=[c for c in template.columns(axis) if c in template.allowed(cat)]
  if axis and (not cols or not any(values.get(c) not in (None,'') for c in cols)):errors.append('missing_variation_axis:'+axis)
 family=values.get(template.column('Size Family'));sub=values.get(template.column('Sub-Size Family'))
 if family:
  subs=template.dropdowns.get(f't_4_{cat}_{family}_Sub-Size Family',[])
  if subs and sub not in subs:errors.append('invalid_size_subfamily')
 for name in ['Base Price - EUR','List Price - EUR','Weight - g','Length - cm','Width - cm','Height - cm']:
  value=values.get(template.column(name))
  if value is not None and float(value)<=0:errors.append('nonpositive:'+name)
 return list(dict.fromkeys(errors))

def build_row(product,parent,cat,description,template,config,override=None):
 override=override or {};facts=extract_facts(product);values={};issues=[];estimates=[];allowed=template.allowed(cat)
 def put(name,value,which=0):
  cols=template.columns(name)
  if len(cols)<=which or cols[which] not in allowed or value is None or value=='':return
  col=cols[which];picked=template.pick(cat,col,value)
  if picked is None:issues.append('invalid_dropdown:'+name+':'+str(value));return
  values[col]=int(picked) if name=='Category' else picked
 def first_property_contains(needle,candidates):
  for col in sorted(allowed):
   if needle not in template.headers[col] or ':' in template.headers[col]:continue
   picked=choose(template.choices(cat,col),candidates)
   if picked is not None:values[col]=picked;return
 sku=str(product.get('sku') or product['id']);parent_id=parent['id'] if parent else product['id']
 put('Category',cat);put('Product type','Normal product');put('Product Name',clean_title(product['name']));put('Contribution Goods',f'SKLADBG-{parent_id}');put('Contribution SKU',f'SKLADBG-{sku}-{product["id"]}');put('Update or Add','Add')
 put('Product Description',description['description'])
 for n,bullet in enumerate(description.get('bullets',[])[:6]):put('Bullet Point',bullet,n)
 urls=image_urls(product) or image_urls(parent or {})
 for n,url in enumerate(urls[:10]):put('SKU Images URL',url,n)
 for n,url in enumerate(urls[:49]):put('Detail Images URL',url,n)
 prices=product.get('prices') or {};unit=int(prices.get('currency_minor_unit',2));currency=prices.get('currency_code')
 if currency!='EUR':raise ValueError('Unsupported currency '+str(currency)+'; refusing conversion without an explicit exchange rate')
 current=Decimal(str(prices.get('price') or 0))/(10**unit);regular=Decimal(str(prices.get('regular_price') or prices.get('price') or 0))/(10**unit)
 if current<=0:raise ValueError('Missing/zero product price')
 put('Base Price - EUR',float(current));put('List Price - EUR',float(max(current,regular)));put('Reference Link',product['permalink'])
 # This is an editable listing quantity, not the site's undisclosed stock count.
 qty=int(override.get('quantity',config.get('listing_quantity',1)));put('Quantity',qty,len(template.columns('Quantity'))-1)
 if qty<1:raise ValueError('Listing quantity must be positive')
 put('Product Identification',override.get('product_identification') or sku)
 pack_count=int(override.get('set_quantity',facts['set_quantity']));put('SKU type','Multi-piece set' if pack_count>1 else 'Single set');put('Individually packed',override.get('individually_packed',config.get('individually_packed')));put('Total packaging quantity',pack_count);put('Packaging unit','piece');put('Total item quantity',pack_count);put('Item unit','piece')
 for name,setting in [('Manufacturer','manufacturer'),('EU Responsible person','eu_responsible_person'),('Country/Region of Origin','country_of_origin'),('Have any products under this goods ID been placed on the EU (or Northern Ireland) market after December 13, 2024?','market_after_2024_12_13')]:
  value=override.get(setting,config.get(setting))
  if name=='Country/Region of Origin' and value=='China':value='Mainland China'
  put(name,value)
 shipping=override.get('shipping_template',config.get('shipping_template'))
 if not shipping:
  options=template.choices(cat,template.column('Shipping Template'))
  if len(options)==1:shipping=options[0]
 put('Shipping Template',shipping);put('Handling Time',config.get('handling_time','2 Days'));put('Fulfillment Channel','I will ship this item myself')
 mats=override.get('materials') or facts['materials']
 first_property_contains(' - Material',mats);first_property_contains(' - Food Contact Material',mats)
 first_property_contains(' - Major Material',mats);first_property_contains(' - Material Type',mats)
 # Exact source percentages, only when the material and percentage occur together.
 source=normalize(text(product['name'])+' '+text(product.get('description','')))
 electric=bool(re.search(r'батери|електр|usb|led|светещ|солар',source))
 # The mapped manual kitchen tools, hand tools and textile objects require no
 # power. Electric/illuminated products must retain their actual source state.
 if not electric:
  first_property_contains(' - Power Supply',['Use Without Electricity','Unpowered'])
  first_property_contains(' - Battery Properties',['Without Battery'])
 elif 'батери' in source:first_property_contains(' - Power Supply',['Dry Battery Power'])
 elif 'usb' in source:first_property_contains(' - Power Supply',['USB Powered'])
 elif 'солар' in source:first_property_contains(' - Power Supply',['Solar Charging'])
 for col in sorted(allowed):
  header=template.headers[col]
  if ':' in header and re.search(r'\d+ - (?:Composition|Cover Material|Liner Material)',header):
   material=header.split(':',1)[1];patterns={'Cotton':r'памук|памуч','Polyester':r'полиестер','Wool':r'вълна|вълнен','Linen':r'лен','Elastane':r'еластан'}
   if material in patterns:
    m=re.search(r'(\d+(?:[.,]\d+)?)\s*%\s*(?:'+patterns[material]+r')|(?:'+patterns[material]+r')\s*(\d+(?:[.,]\d+)?)\s*%',source)
    if m and not any(property_group(template.keys[c])==property_group(template.keys[col]) and template.headers[c]==header for c in values):values[col]=float((m[1] or m[2]).replace(',','.'))
 for name,value in [('Color',(description.get('color') or (facts['colors'][0] if len(facts['colors'])==1 else None))),('26 - Pattern',None),('Shape',description.get('shape'))]:
  if value:
   for col in template.columns(name):
    if col in allowed:
     options=template.choices(cat,col);picked=choose(options,[value,'Gray' if value=='Grey' else value])
     if picked is not None:values[col]=picked;break
 # Infer visible shape or confirmed attributes only, then honor per-category choices.
 for col in sorted(allowed):
  header=template.headers[col]
  if ' - Shape' in header:
   shape=override.get('shape') or description.get('shape') or ('Round' if re.search(r'кръгл',source) else 'Rectangular' if re.search(r'правоъгъл',source) else 'Square' if re.search(r'квадрат',source) else None)
   if shape:
    selected=template.pick(cat,col,shape)
    if selected is not None:values[col]=selected
  if ' - Applicable Age Group' in header and override.get('age_group'):values[col]=template.pick(cat,col,override['age_group'])
 dims=facts['dimensions'];package=override.get('package_cm') or (dims['values_cm'] if dims and dims['is_package'] and len(dims['values_cm'])==3 else config.get('default_package_cm'))
 if package:
  for name,v in zip(['Length - cm','Width - cm','Height - cm'],package):put(name,float(v))
  if not override.get('package_cm') and not (dims and dims['is_package']):estimates.append('package_dimensions_default')
 weight=override.get('package_weight_g') or config.get('default_package_weight_g')
 if weight:put('Weight - g',float(weight));estimates.append('package_weight_default') if not override.get('package_weight_g') else None
 # Product size chart fields use product dimensions; shipping defaults do not.
 if dims:
  for col in sorted(allowed):
   header=template.headers[col]
   if ' - Product - Length' in header:values[col]=dims['values_cm'][0]
   if ' - Product - Width' in header and len(dims['values_cm'])>1:values[col]=dims['values_cm'][1]
  for col in template.columns('Unit'):
   if col in allowed:
    picked=choose(template.choices(cat,col),['cm-g-ml','cm'])
    if picked:values[col]=picked
 theme_options=template.choices(cat,template.column('Variation Theme'));required=template.required.get(cat,set());size_col=template.column('Size')
 size_required=size_col in required
 theme='Size' if size_required else 'Items'
 if theme not in theme_options:theme='Size' if 'Size' in theme_options else 'Model' if 'Model' in theme_options else None
 if not theme:issues.append('no_supported_variation_theme')
 else:
  put('Variation Theme',theme)
  if theme=='Items':put('Items',clean_title(product['name'])[:100])
  elif theme=='Model':put('Model',sku)
  elif theme=='Size':
   m=re.search(r'(?:№|номер|size)\s*(\d+)',source)
   size=override.get('size') or (m[1] if m else dims['label'] if dims else None)
   if size:put('Size',size)
   family='101 - Custom size';put('Size Family',family)
   sub_options=template.dropdowns.get(f't_4_{cat}_{family}_Sub-Size Family',[])
   if len(sub_options)==1:put('Sub-Size Family',sub_options[0])
 if parent:
  # Each real purchasable child receives a separate row; use actual child attributes.
  attrs=product.get('attributes') or []
  size=next((a.get('value') or a.get('option') for a in attrs if 'size' in str(a.get('name','')).lower() or 'размер' in str(a.get('name','')).lower()),None)
  color=next((a.get('value') or a.get('option') for a in attrs if 'color' in str(a.get('name','')).lower() or 'цвят' in str(a.get('name','')).lower()),None)
  actual_theme='Size × Color' if size and color else 'Size' if size else 'Color' if color else theme
  put('Variation Theme',actual_theme)
  if size:put('Size',size)
  if color:put('Color',color,len(template.columns('Color'))-1)
 # Overrides are keyed by exact field header or numeric column number.
 for name,value in override.get('fields',{}).items():
  if str(name).isdigit():
   col=int(name)
   if col not in allowed:issues.append('disabled_override_column:'+str(col));continue
   picked=template.pick(cat,col,value)
   if picked is None:issues.append('invalid_override:'+str(name))
   else:values[col]=picked
  else:put(name,value)
 if config.get('estimate_missing_attributes'):
  from field_estimates import complete_required
  complete_required(product,cat,description,template,config,facts,values,estimates,override)
 # Re-check final state: a recovered variation theme must not retain an old error.
 if values.get(template.column('Variation Theme')):issues=[x for x in issues if x!='no_supported_variation_theme']
 issues.extend(validate_record(template,cat,values))
 conditional=required_missing(template,cat,values)
 return values,{'id':product['id'],'sku':sku,'url':product['permalink'],'name':product['name'],'category_id':cat,'category':template.categories[cat],'description_source':description['source'],'issues':list(dict.fromkeys(issues)),'estimates':estimates,'conditional_fields_to_review':list(dict.fromkeys(conditional)),'facts':facts}
