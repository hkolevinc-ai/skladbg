#!/usr/bin/env python3
"""SkladBG -> supplied Temu template. Python 3.11+, standard library only."""
import argparse,collections,concurrent.futures,csv,datetime,json,logging,os,pathlib,sys
from category_rules import classify
from descriptions import analyze_images,from_source,image_urls,reviewed_description
from http_client import HttpClient
from product_fields import build_row,extract_facts
from temu_template import TemuTemplate
LOG=logging.getLogger('skladbg')
ROOT=pathlib.Path(__file__).resolve().parent
FIELDS='id,parent,type,name,sku,permalink,description,short_description,prices,categories,attributes,variations,images,is_in_stock,is_purchasable,is_on_backorder,add_to_cart'
def write_json(path,data):pathlib.Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def write_csv(path,records,fields):
 with open(path,'w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
  for record in records:
   # Neutralize spreadsheet formulas in CSV reports from scraped strings.
   record={k:(json.dumps(v,ensure_ascii=False) if isinstance(v,(list,dict)) else v) for k,v in record.items()}
   record={k:("'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v) for k,v in record.items()};w.writerow(record)
def run(args):
 config=json.loads(pathlib.Path(args.config).read_text());overrides=json.loads(pathlib.Path(args.overrides).read_text())
 reviewed_path=ROOT/'reviewed_descriptions.json';reviewed=json.loads(reviewed_path.read_text()) if reviewed_path.exists() else {}
 out=pathlib.Path(args.output);out.mkdir(parents=True,exist_ok=True)
 template=TemuTemplate(args.template);write_json(out/'template_schema.json',template.schema_report())
 for key,name in [('manufacturer','manufacturer_choices'),('eu_responsible_person','eu_responsible_choices')]:
  if config.get(key) and config[key] not in template.schema_report()[name]:raise ValueError(key+' is not present in this template dropdown')
 if args.vision and not os.environ.get('OPENAI_API_KEY'):raise ValueError('Vision requested but OPENAI_API_KEY is missing. Add a GitHub Actions secret or run without --vision.')
 client=HttpClient(config.get('site_url','https://skladbg.net'),workers=int(config.get('workers',4)))
 if args.catalog:
  products=json.loads(pathlib.Path(args.catalog).read_text());counts={'api_total':len(products),'fetched':len(products),'unique_ids':len({p['id'] for p in products}),'mode':'saved_snapshot'}
  if counts['unique_ids']!=len(products):raise ValueError('Duplicate IDs in saved snapshot')
 else:products,counts=client.collection(_fields=FIELDS)
 write_json(out/'catalog_snapshot.json',products)
 selected=[];skipped=[];parent_cache={};stock_count=0
 for product in products:
  if product.get('type')=='variation':continue
  if not product.get('is_in_stock') or product.get('is_on_backorder') or product.get('is_purchasable') is False:
   skipped.append({'id':product['id'],'name':product['name'],'url':product['permalink'],'reason':'out_of_stock_or_not_purchasable'});continue
  stock_count+=1
  cat,reason=classify(product,template.categories,overrides)
  if cat is None:skipped.append({'id':product['id'],'name':product['name'],'url':product['permalink'],'reason':reason});continue
  if product.get('type')=='variable':
   try:children=client.variants(product)
   except Exception as exc:
    skipped.append({'id':product['id'],'name':product['name'],'url':product['permalink'],'reason':'variation_fetch_failed:'+str(exc)});continue
   for child in children:
    if child.get('is_in_stock') and not child.get('is_on_backorder') and child.get('is_purchasable') is not False:
     child={**child,'categories':product.get('categories',[])};selected.append((child,product,cat))
  else:selected.append((product,None,cat))
 if not selected:raise ValueError('No in-stock products match template categories; refusing to create an empty output')
 full_selected_count=len(selected)
 if args.limit:selected=selected[:args.limit]
 LOG.info('Selected %s rows (%s before --limit) from %s available products',len(selected),full_selected_count,stock_count)
 vision_limit=args.vision_limit if args.vision_limit is not None else int(config.get('vision_limit',20))
 records=[];audit=[];descriptions=[];vision_attempts=0;vision_errors=[]
 for n,(product,parent,cat) in enumerate(selected,1):
  facts=extract_facts(product);description=reviewed_description(product,reviewed) or from_source(product,cat,facts)
  if args.vision and description['source']!='reviewed_images' and (vision_limit==0 or vision_attempts<vision_limit):
   vision_attempts+=1
   try:description=analyze_images(product,cat,facts,client,args.vision_cache,config.get('vision_model','gpt-4.1-mini'))
   except Exception as exc:
    vision_errors.append({'id':product['id'],'reason':str(exc)});LOG.warning('Vision failed for %s: %s. Source description retained.',product['id'],type(exc).__name__)
  descriptions.append({'id':product['id'],'name':product['name'],'url':product['permalink'],**description})
  try:record,report=build_row(product,parent,cat,description,template,config,overrides.get(str(product['id'])))
  except Exception as exc:
   skipped.append({'id':product['id'],'name':product['name'],'url':product['permalink'],'reason':'row_build_failed:'+str(exc)});continue
  if not image_urls(product) and not image_urls(parent or {}):
   skipped.append({'id':product['id'],'name':product['name'],'url':product['permalink'],'reason':'no_product_images'});continue
  records.append(record);audit.append(report)
  if n%100==0:LOG.info('Prepared %s/%s rows',n,len(selected))
 if not records:raise ValueError('No valid product rows; see source data and template')
 maxrows=min(template.capacity,int(config.get('max_rows_per_file',4996)))
 if maxrows<1:raise ValueError('max_rows_per_file must be positive')
 files=[]
 # All selected listings are retained. Rows needing mandatory information are
 # explicitly marked in the report; the entire workbook is named DRAFT.
 issues_count=sum(bool(r['issues']) for r in audit)
 prefix='TEMU_SKLADBG_DRAFT' if issues_count else 'TEMU_SKLADBG'
 for i in range(0,len(records),maxrows):files.append(str(template.write(out/f'{prefix}_{i//maxrows+1:03d}.xlsx',records[i:i+maxrows]).name))
 for i,report in enumerate(audit):report['output_file']=files[i//maxrows];report['excel_row']=i%maxrows+5
 write_json(out/'product_audit.json',audit);write_json(out/'descriptions.json',descriptions);write_json(out/'skipped.json',skipped)
 write_csv(out/'review_required.csv',[r for r in audit if r['issues'] or r['estimates'] or r['conditional_fields_to_review']],['id','sku','name','url','category_id','category','output_file','excel_row','description_source','issues','estimates','conditional_fields_to_review'])
 write_csv(out/'skipped.csv',skipped,['id','name','url','reason'])
 write_csv(out/'descriptions.csv',descriptions,['id','name','url','source','description','bullets','visible_features','color','shape'])
 summary={**counts,'completed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'template_categories':len(template.categories),'in_stock_purchasable_products':stock_count,'matched_before_limit':full_selected_count,'exported_rows':len(records),'rows_with_missing_required_or_invalid_fields':issues_count,'rows_with_estimates':sum(bool(r['estimates']) for r in audit),'description_sources':dict(collections.Counter(r['description_source'] for r in audit)),'vision_attempts':vision_attempts,'vision_errors':vision_errors,'categories_exported':dict(collections.Counter(r['category'] for r in audit)),'skipped_reasons':dict(collections.Counter(r['reason'].split(':')[0] for r in skipped)),'output_files':files,'listing_quantity_is_configured_not_real_stock':config.get('listing_quantity',1),'upload_ready':issues_count==0,'conditional_requirements_need_review':True}
 write_json(out/'summary.json',summary);LOG.info('Done: %s rows, %s workbooks, %s rows require additional data',len(records),len(files),issues_count)
 print(json.dumps(summary,ensure_ascii=False,indent=2))
 return summary
def parse_args():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--template',default=str(ROOT/'template.xlsx'));p.add_argument('--config',default=str(ROOT/'config.json'));p.add_argument('--overrides',default=str(ROOT/'product_overrides.json'));p.add_argument('--output',default=str(ROOT/'output'));p.add_argument('--catalog',help='Use a previously downloaded JSON snapshot for reproducible testing');p.add_argument('--limit',type=int,default=0,help='Export only the first N matching rows; 0 means all');p.add_argument('--vision',action='store_true');p.add_argument('--vision-limit',type=int,help='Maximum images-analysis requests; 0 means all');p.add_argument('--vision-cache',default=str(ROOT/'vision_cache'));p.add_argument('--verbose',action='store_true');return p.parse_args()
if __name__=='__main__':
 args=parse_args();logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,format='%(asctime)s %(levelname)s %(message)s')
 try:run(args)
 except Exception as exc:LOG.error('%s: %s',type(exc).__name__,exc);sys.exit(1)
