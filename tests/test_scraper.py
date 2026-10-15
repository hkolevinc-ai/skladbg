import contextlib,io,json,pathlib,tempfile,unittest,zipfile,xml.etree.ElementTree as ET
from unittest.mock import patch
from category_expansion import classify
from descriptions import analyze_images,from_source
from http_client import HttpClient
from product_fields import build_row,extract_facts,required_missing
from temu_template import TemuTemplate,NS,rows
ROOT=pathlib.Path(__file__).resolve().parents[1]
def product(name='Гевгир алпака 22 см',id=123,stock=True):
 return {'id':id,'name':name,'sku':'00123','type':'simple','permalink':'https://skladbg.net/produkt/test/','is_in_stock':stock,'is_purchasable':True,'is_on_backorder':False,'description':'','short_description':'','categories':[],'attributes':[],'variations':[],'images':[{'src':'https://skladbg.net/test.jpg'}],'prices':{'price':'350','regular_price':'450','currency_code':'EUR','currency_minor_unit':2}}
class ScraperTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.template=TemuTemplate(ROOT/'template.xlsx');cls.config=json.loads((ROOT/'config.json').read_text())
 def cat(self,name,**kwargs):return classify(product(name,**kwargs),self.template.categories)[0]
 def test_supported_specific_categories(self):
  for name,expected in [('Футболна топка №5',36731),('Гевгир алпака 22 см',9995),('Калъф за дрехи с цип',12822),('Дъска за сервиране',54423),('Моп с кофа',12985),('Комплект от 3 стъклени чаши',10579),('Бамбукова дъска за рязане',39118),('Купа меламин 23 х 6 см',10728)]:
   with self.subTest(name=name):self.assertEqual(self.cat(name),expected)
 def test_reject_similar_wrong_products(self):
  for name in ['Магическа дъска за рисуване','Плюшена играчка в кутия','Кухненски чук','Кофа с цедка','Лампа с форма на чаша','Калъф за куфар','Колан за кръст','Ваза с цветя','Комплект цветни моливи с линия','Форма за сладки','Ключодържател амулет','Кутия за цигари']:
   with self.subTest(name=name):self.assertIsNone(self.cat(name))
 def test_no_category_outside_template(self):self.assertIsNone(classify(product('Футболна топка'),{9995})[0])
 def test_explicit_override_still_checks_allowlist(self):self.assertIsNone(classify(product(),self.template.categories,{'123':{'category_id':9999999}})[0])
 def test_decimal_dimensions_and_explicit_set_quantity(self):
  f=extract_facts(product('Комплект от 4 стъклени купи 23 х 17 х 5,5 см'))
  self.assertEqual(f['set_quantity'],4);self.assertEqual(f['dimensions']['values_cm'],[23.0,17.0,5.5]);self.assertIn('Glass',f['materials'])
 def test_display_stock_is_not_sale_set(self):self.assertEqual(extract_facts(product('Чаша 12 броя в стек'))['set_quantity'],1)
 def test_explicit_set_abbreviations(self):
  for name,count in [('Сет от 4 кутии',4),('Комлект 6 броя лъжици',6),('Ножчета (12бр.к-кт)',12)]:self.assertEqual(extract_facts(product(name))['set_quantity'],count)
 def test_price_currency_and_shipping_facts(self):
  p=product();f=extract_facts(p);d=from_source(p,9995,f);row,audit=build_row(p,None,9995,d,self.template,self.config)
  self.assertEqual(row[self.template.column('Base Price - EUR')],3.5);self.assertEqual(row[self.template.column('List Price - EUR')],4.5)
  self.assertEqual(row[self.template.column('Shipping Template')],'Lazur');self.assertEqual(row[self.template.columns('Quantity')[-1]],1)
  self.assertEqual(row[self.template.column('Country/Region of Origin')],'Mainland China');self.assertGreater(row[self.template.column('Weight - g')],0)
  self.assertNotIn(self.template.column('Manufacturer'),row);self.assertNotIn(self.template.column('EU Responsible person'),row)
  self.assertEqual(audit['issues'],[]);self.assertEqual(required_missing(self.template,9995,row),[])
 def test_shipping_defaults_do_not_become_product_dimensions(self):
  p=product('Гевгир');d=from_source(p,9995,extract_facts(p));cfg={**self.config,'default_package_cm':[20,20,20],'default_package_weight_g':1000}
  row,a=build_row(p,None,9995,d,self.template,cfg)
  self.assertEqual(row[self.template.column('Weight - g')],1000);self.assertEqual(a['facts']['dimensions'],None);self.assertIn('package_dimensions_default',a['estimates'])
 def test_repeated_required_property_needs_one_value(self):
  cat=10728;required=[x for x in self.template.required[cat] if self.template.headers[x]=='121 - Material'];row={required[0]:'Melamine'}
  self.assertFalse(any(x=='121 - Material' for x in required_missing(self.template,cat,row)))
 def test_unknown_currency_is_not_silently_converted(self):
  p=product();p['prices']['currency_code']='BGN'
  with self.assertRaisesRegex(ValueError,'currency'):build_row(p,None,9995,from_source(p,9995,extract_facts(p)),self.template,self.config)
 def test_writer_preserves_metadata_validations_and_reserved_rows(self):
  p=product();row,_=build_row(p,None,9995,from_source(p,9995,extract_facts(p)),self.template,self.config)
  with tempfile.TemporaryDirectory() as tmp:
   out=self.template.write(pathlib.Path(tmp)/'test.xlsx',[row]);z=zipfile.ZipFile(out)
   for name in z.namelist():
    if name!=self.template.sheets['Template']:self.assertEqual(z.read(name),self.template.z.read(name),name)
   root=ET.fromstring(z.read(self.template.sheets['Template']));parsed=dict(rows(z.read(self.template.sheets['Template']),self.template.strings))
   self.assertEqual(parsed[5][5],'9995');self.assertEqual(parsed[5][14],'SKLADBG-00123-123');self.assertTrue(root.find('s:dataValidations',NS) is not None)
   original=ET.fromstring(self.template.template_xml)
   for rn in range(1,5):
    self.assertEqual(ET.tostring(root.find(f's:sheetData/s:row[@r="{rn}"]',NS)).rstrip(),ET.tostring(original.find(f's:sheetData/s:row[@r="{rn}"]',NS)).rstrip())
   self.assertIsNotNone(root.find('s:sheetData/s:row[@r="5"]/s:c[@r="F5"]/s:f',NS))
 def test_pagination_failure_prevents_partial_export(self):
  client=HttpClient(workers=1)
  with patch.object(client,'json',side_effect=[([product()],{'X-WP-Total':'2','X-WP-TotalPages':'2'}),([], {})]):
   with self.assertRaisesRegex(ValueError,'Empty'):client.collection()
 def test_duplicates_prevent_export(self):
  client=HttpClient(workers=1)
  with patch.object(client,'json',return_value=([product(),product()],{'X-WP-Total':'2','X-WP-TotalPages':'1'})):
   with self.assertRaisesRegex(ValueError,'unique'):client.collection()
 def test_missing_pagination_headers_prevent_export(self):
  client=HttpClient(workers=1)
  with patch.object(client,'json',return_value=([product()],{})):
   with self.assertRaisesRegex(ValueError,'Pagination headers missing'):client.collection()
 def test_vision_sends_actual_images_and_caches(self):
  seen=[]
  class Fake:
   def json(self,url,payload,headers):
    seen.append(payload);data={'description':'Кръгъл гевгир с отвори.','bullets':['Видими отвори'],'visible_features':['Отвори'],'color':None,'shape':'Round'}
    return {'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(data)}]}]},{}
  with tempfile.TemporaryDirectory() as tmp,patch.dict('os.environ',{'OPENAI_API_KEY':'test-only-not-real'}):
   p=product();facts=extract_facts(p);a=analyze_images(p,9995,facts,Fake(),tmp);b=analyze_images(p,9995,facts,Fake(),tmp)
   self.assertEqual(a,b);self.assertEqual(len(seen),1);self.assertEqual(seen[0]['input'][0]['content'][1]['type'],'input_image');self.assertEqual(seen[0]['input'][0]['content'][1]['image_url'],'https://skladbg.net/test.jpg');self.assertEqual(a['source'],'vision')
 def test_stock_filter_end_to_end(self):
  from argparse import Namespace
  from scraper import run
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'input.json';path.write_text(json.dumps([product(id=1),product(id=2,stock=False),product(name='Плюшена играчка',id=3)]))
   args=Namespace(config=ROOT/'config.json',overrides=ROOT/'product_overrides.json',output=pathlib.Path(tmp)/'out',template=ROOT/'template.xlsx',vision=False,catalog=path,limit=0,vision_limit=None,vision_cache=pathlib.Path(tmp)/'cache')
   with contextlib.redirect_stdout(io.StringIO()):summary=run(args)
   self.assertEqual(summary['exported_rows'],1);self.assertEqual(summary['in_stock_purchasable_products'],2);self.assertTrue(summary['mandatory_fields_complete']);self.assertEqual(summary['rows_with_missing_required_or_invalid_fields'],0);self.assertNotIn('DRAFT',summary['output_files'][0])
 def test_required_compound_variation_and_percent_sum(self):
  for name,cat in [('Комплект спално бельо',11893),('Баскетболна топка',36322),('Калъфка за възглавница',11845),('Кутия за подарък',39880)]:
   p=product(name);row,a=build_row(p,None,cat,from_source(p,cat,extract_facts(p)),self.template,self.config)
   self.assertEqual(a['issues'],[],name);self.assertEqual(required_missing(self.template,cat,row),[],name)
   self.assertIn(row[self.template.column('Variation Theme')],self.template.choices(cat,self.template.column('Variation Theme')))
   from product_fields import property_group
   groups={}
   for col in self.template.required[cat]|self.template.active_conditional(cat,row):
    if ':' in self.template.headers[col] and 'Property:' in self.template.keys[col]:groups.setdefault(property_group(self.template.keys[col]),[]).append(col)
   for cols in groups.values():self.assertAlmostEqual(sum(float(row.get(c,0)) for c in cols),100)
 def test_source_values_override_estimates(self):
  p=product('Калъфка за възглавница 70 х 50 см, 100% памук');cat=11845
  row,a=build_row(p,None,cat,from_source(p,cat,extract_facts(p)),self.template,self.config,{'package_cm':[22,15,5],'package_weight_g':220,'fields':{'206 - Closure Type':'Envelope'}})
  self.assertEqual(row[self.template.column('Weight - g')],220)
  self.assertEqual(row[self.template.column('Length - cm')],22)
  self.assertEqual(row[self.template.column('206 - Closure Type')],'Envelope')
  self.assertEqual(a['issues'],[])
 def test_conditional_requirements_activate(self):
  cat=10728;row={self.template.column('Country/Region of Origin'):'Mainland China',self.template.column('121 - Material'):'Stainless Steel'}
  missing=required_missing(self.template,cat,row)
  self.assertIn('Province of Origin',missing)
  self.assertIn('7085 - Stainless Steel Grade',missing)
  row[self.template.column('121 - Material')]='Plastic';row[self.template.column('Country/Region of Origin')]='Bulgaria'
  self.assertNotIn('Province of Origin',required_missing(self.template,cat,row))
  self.assertNotIn('7085 - Stainless Steel Grade',required_missing(self.template,cat,row))
 def test_category_corrections(self):
  for name,expected in [('Изкуствена коледна елха лукс, 120 см',13001),('Силиконова подложка за месене, 40 х 50 см',39118),('Дървена лъжица за спагети',9999),('Лъжица за чай',10682),('Дамска барета ангора',29279),('Кутия за подарък',39880),('Комплект от 4 кутии за съхранение, 300 мл',10353)]:
   self.assertEqual(self.cat(name),expected,name)
  for name in ['Мъжка чанта, която се носи на колан','Сгъваем нож играчка','Шапка за плуване','Детска капела','Дамска капела','Магнит коледен снежко','Конци в квадратна кутия','Кутия музикална куфарче','Канче с мраморно покритие']:
   self.assertIsNone(self.cat(name),name)
 def test_blank_required_blocks_export(self):
  from argparse import Namespace
  from scraper import run
  with tempfile.TemporaryDirectory() as tmp:
   tmp=pathlib.Path(tmp);p=product();(tmp/'input.json').write_text(json.dumps([p]));cfg={**self.config,'estimate_missing_attributes':False,'estimate_missing_packages':False};(tmp/'config.json').write_text(json.dumps(cfg))
   args=Namespace(config=tmp/'config.json',overrides=ROOT/'product_overrides.json',output=tmp/'out',template=ROOT/'template.xlsx',vision=False,catalog=tmp/'input.json',limit=0,vision_limit=None,vision_cache=tmp/'cache')
   with self.assertRaisesRegex(ValueError,'Mandatory validation failed'):run(args)
   self.assertFalse(list((tmp/'out').glob('*.xlsx')));self.assertTrue((tmp/'out'/'validation_errors.csv').exists())
 def test_invalid_override_blocks_export_row(self):
  p=product();row,a=build_row(p,None,9995,from_source(p,9995,extract_facts(p)),self.template,self.config,{'fields':{'121 - Material':'Made-up material'}})
  self.assertTrue(any(x.startswith('invalid_dropdown:') for x in a['issues']))
 def test_title_cleaning_never_returns_blank(self):
  from descriptions import clean_title
  self.assertEqual(clean_title('12 броя в стек'),'12 броя в стек')
 def test_multiple_exports_preserve_template_zip_members(self):
  p=product();row,_=build_row(p,None,9995,from_source(p,9995,extract_facts(p)),self.template,self.config)
  with tempfile.TemporaryDirectory() as tmp:
   for i in range(2):
    path=self.template.write(pathlib.Path(tmp)/f'{i}.xlsx',[row]);z=zipfile.ZipFile(path)
    self.assertEqual(z.read('xl/workbook.xml'),self.template.z.read('xl/workbook.xml'))
if __name__=='__main__':unittest.main()

