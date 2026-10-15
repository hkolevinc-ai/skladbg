import concurrent.futures,json,logging,time,urllib.error,urllib.parse,urllib.request
LOG=logging.getLogger(__name__)
class HttpClient:
 def __init__(self,base_url='https://skladbg.net',timeout=45,retries=4,workers=4):
  self.base=base_url.rstrip('/');self.timeout=timeout;self.retries=retries;self.workers=workers
 def json(self,url,payload=None,headers=None):
  body=json.dumps(payload,ensure_ascii=False).encode() if payload is not None else None
  safe_headers={'User-Agent':'SkladBG-Temu-Catalog/1.0 (public product catalog)','Accept':'application/json',**(headers or {})}
  if body:safe_headers['Content-Type']='application/json'
  for attempt in range(self.retries):
   try:
    request=urllib.request.Request(url,data=body,headers=safe_headers)
    with urllib.request.urlopen(request,timeout=self.timeout) as response:return json.load(response),dict(response.headers)
   except (urllib.error.URLError,TimeoutError,json.JSONDecodeError) as exc:
    if isinstance(exc,urllib.error.HTTPError) and exc.code not in {408,425,429,500,502,503,504}:raise
    if attempt+1==self.retries:raise
    delay=min(15,2**attempt)
    LOG.warning('Request failed; retry %s/%s in %ss (%s)',attempt+1,self.retries,delay,type(exc).__name__)
    time.sleep(delay)
 def products_url(self,page=1,**params):
  return self.base+'/wp-json/wc/store/v1/products?'+urllib.parse.urlencode({'per_page':100,'orderby':'id','order':'asc','page':page,**params},doseq=True)
 def collection(self,**params):
  first,headers=self.json(self.products_url(1,**params))
  if not isinstance(first,list):raise ValueError('API did not return a product list')
  headers={k.lower():v for k,v in headers.items()}
  if 'x-wp-total' not in headers or 'x-wp-totalpages' not in headers:raise ValueError('Pagination headers missing; refusing an incomplete export')
  total=int(headers.get('x-wp-total',len(first)));pages=int(headers.get('x-wp-totalpages',1))
  products=list(first)
  with concurrent.futures.ThreadPoolExecutor(max_workers=self.workers) as pool:
   def get(n):return n,self.json(self.products_url(n,**params))[0]
   for page,data in pool.map(get,range(2,pages+1)):
    if not isinstance(data,list) or not data:raise ValueError(f'Empty or invalid catalog page {page}/{pages}')
    products.extend(data)
    if page%10==0 or page==pages:LOG.info('Fetched %s/%s pages; %s/%s records',page,pages,len(products),total)
  ids=[p['id'] for p in products]
  if len(ids)!=len(set(ids)) or len(ids)!=total:raise ValueError(f'Catalog changed or pagination incomplete: expected {total}; received {len(ids)}; unique {len(set(ids))}. Run again.')
  return products,{'api_total':total,'api_pages':pages,'fetched':len(products),'unique_ids':len(set(ids))}
 def product(self,product_id):return self.json(self.base+f'/wp-json/wc/store/v1/products/{product_id}')[0]
 def variants(self,parent):
  refs=parent.get('variations') or []
  found=[]
  for ref in refs:
   ident=ref.get('id') if isinstance(ref,dict) else ref
   child=self.product(ident)
   if child.get('type')!='variation' and int(child.get('parent') or 0)!=int(parent['id']):raise ValueError(f'Unexpected variation response for {ident}')
   found.append(child)
  if not found:raise ValueError('Variable product has no public variation IDs; skipped for review instead of guessing combinations')
  return found
