"""Reviewed product-type synonyms, restricted to categories in the workbook."""
import re
from category_rules import normalize,classify as legacy_classify

RULES=[
 (13001,r'изкуствен[ао]?(?:\s+коледн[ао])?\s+елх|коледна елха.*(?:лукс|височ|стойка)|елха.*(?:лукс|см|метр)'),
 (13031,r'(?:колед.*|декоратив.*колед.*)(?:снежко|снежен|къщич|къщ[аи]|джудже|гном|елен|ангел|дядо)|(?:музикален|светещ|танцуващ).*дядо коледа|дядо коледа'),
 (13027,r'дървен[аои].*коледна.*украса|коледна украса.*(?:звънче|камбан|елхич|снежинка|бастун)|колед.*(?:висул|висулк)|висулк.*елха'),
 (13003,r'коледен ботуш|коледно чорапче|колед.*чувал.*чорап'),
 (12258,r'букет|изкуствен[аои].*цвет|роз[аи].*(?:\d|букет)|цвет[ея].*(?:букет|роз|лале)'),
 (12262,r'изкуствен[аои].*(?:растение|зеленина|растения|клон|лист)|декоратив.*изкуствен.*раст|сукулент'),
 (12179,r'бижутерк|декоративна кутия|декоративни кутии|дървена къщичка за ключове'),
 (54156,r'контейнер|кути[яи].*(?:съхранение|съхранен|организ)|контейнер.*хран'),
 (10353,r'комплект.*(?:кути[яи]|контейнер).*(?:храна|хранител|съхранение)|(?:кути[яи]|контейнер).*храна.*комплект'),
 (10728,r'бонбониер|фруктиер|купич|чаша за сладолед'),
 (10586,r'канче|чашк.*чай'),(10579,r'стъклени(?:\s+[а-я]+){0,2}\s*чаш|стъклен[аи]\s+чашк'),
 (11344,r'лъжичк|лъжици'),(10682,r'(?:чай|чаени|кафе).*лъжич|лъжич.*(?:кафе|чай)'),
 (10000,r'силиконов[аи].*щипк|щипк.*(?:сладки|салат|грил|барбекю|храна|паста)'),
 (10006,r'комплект.*(?:лъжици|готвене|черпаци)|сет.*кухненск.*прибор'),
 (10327,r'сушилник.*прибор|поставк.*прибор'),
 (12698,r'сушилник.*(?:съдове|чини)|метален сушилник.*(?:ниво|чини)|поставка.*чинии'),
 (39118,r'силиконова подложка.*(?:месене|точене|тесто)|дъски.*(?:рязане|кухн)'),
 (10025,r'силиконов[аи].*ръкавиц.*горещ|ръкохватк|готварска ръкавица'),
 (12948,r'четка.*мивка|четка.*хром|четк.*фуга|четка.*съд|четк.*шиш'),
 (12906,r'микрофибър|микрофибърна кърпа|кърп.*(?:миене|почистване)|почистване.*кърп'),
 (12879,r'гъба.*почист|телчета.*съд'),
 (12884,r'комплект.*(?:лопатка.*четка|четка.*лопатка)|универсална бърсалка|метличк'),
 (12985,r'комплект.*(?:кофа.*моп|моп.*кофа)|спинмоп'),
 (12749,r'кошниц[аи].*пране|кош[а-я ]*\s+за пране'),(12753,r'панер.*пране'),
 (11801,r'кош.*отпадъц|koш.*отпадъц'),
 (12822,r'вакуумен плик.*дрехи|калъф.*дрехи'),
 (11927,r'щипк.*чаршаф|фиксатор.*чаршаф|ластиц.*чаршаф'),
 (12009,r'покривало.*диван|покривало.*легло'),
 (11893,r'спален комплект|спално бельо|спален.*чаршаф.*калъф'),
 (11894,r'калъфки.*спал|калъфк[аи].*възглавниц'),
 (11812,r'хавлиен[аои].*кърп|кърпи.*баня'),
 (11876,r'възглавниц.*(?:хаги|стич|детск.*плюш|плюшен.*играч)'),
 (11915,r'възглавници|възглавничк'),
 (12797,r'рафт.*(?:стелаж|етажер)|етажерки'),
 (15570,r'нож.*балатум|джобен нож|сгъваем нож|макетен нож|макетно ножче'),
 (15525,r'френски ключ|регулируем.*гаеч|гаеч.*регулируем'),
 (15528,r'шестограм|лимбуси|ключ.*шестостен'),
 (15531,r'гедор|гидор|ключ.*вложк|вложки'),
 (15532,r'динамометрич'),
 (7327,r'отвертк'),
 (15465,r'гумен чук|дървен чук|киянк'),
 (24966,r'лейк|съд.*полив'),(24962,r'градински маркуч|маркуч.*полив'),
 (38097,r'тенис.*ракета|ракета.*корт'),
 (30611,r'шапка малборо|бейзбол.*шапк|шапк.*козирк'),
 (30618,r'плетена шапка|зимна шапка'),
 (29279,r'дамск.*(?:плетен|зимн).*шапк'),
 (54804,r'дамска барета|дамска капела'),
 (31019,r'раница.*лаптоп'),(40334,r'училищ.*раница|ученическ.*раница'),
 (39159,r'дамска раница'),(40414,r'мъжка раница'),
 (12193,r'декоративна табел|табел.*(?:дърв|надпис)|коледен надпис'),
 (40380,r'коледни стикери|стенн.*пано|стикер.*стена'),
 (13004,r'поставка.*коледен чорап'),
]
COMPILED=[(c,re.compile(p)) for c,p in RULES]
FORBIDDEN_HEAD=re.compile(r'ключодърж|магнит|плюшена играчка|декоративен сувенир|ваза|солнич|оливерник|диадема|лепило|свещ|прожектор|конци|торбичка|торбички|ароматизатор|подложка.*мишк|ренде|захарниц|іграчка|играчка|подложка.*елха')
def classify(product,allowed,overrides=None):
 cat,reason=legacy_classify(product,allowed,overrides)
 if overrides and overrides.get(str(product['id']),{}).get('category_id') is not None:return cat,reason
 s=normalize(product['name']).replace('koш','кош')
 if re.search(r'кути[яи].*подар|подар.*кути[яи]',s) and 39880 in allowed:return 39880,'specific_gift_wrap_box'
 if re.search(r'^(?:мъжка |дамска |детска )?чанта|клечки за уши|цветоулавящ|^ренде|^захарниц|кутия.*(?:клечки|тампони)',s):return None,'product_type_not_in_template'
 if cat in {54156,5436} and re.search(r'конци|свещ|гривни|музикална|кутия.*масло|кутия.*торта|аромат|пудра|четк.*зъб|поставк.*телефон',s):return None,'product_type_not_in_template'
 if cat==54156 and re.search(r'(?:комплект|сет).*кути|кути.*(?:комплект|сет)',s):
  if re.search(r'съхранение|\bмл\b|\bml\b|\bпвц\b',s) and 10353 in allowed:return 10353,'specific_food_container_set'
 if cat==5436:
  if re.search(r'етажерк|рафт',s) and 12797 in allowed:return 12797,'specific_shelf_type'
  if re.search(r'готварск.*съд|сушилник',s) and 12698 in allowed:return 12698,'specific_utensil_rack_type'
  if re.search(r'кути|съхранение',s) and 54156 in allowed:return 54156,'specific_storage_box_type'
  return None,'organizer_is_not_utility_rack'
 if cat==54804 and not re.search(r'костюм|карнавал|маскарад',s):
  if re.search(r'ангора|плетен|зимн',s) and 29279 in allowed:return 29279,'specific_womens_knitted_hat'
  return None,'ordinary_hat_is_not_costume_hat'
 if cat==34864:
  if re.search(r'детск|бомбе|плуване|баня',s):return None,'hat_type_not_in_template'
  if re.search(r'\balo\b|\bla\b',s) and 30611 in allowed:return 30611,'specific_baseball_cap'
  if re.search(r'идиотк',s) and 30612 in allowed:return 30612,'specific_bucket_hat'
 if cat in {11344,10680}:
  if re.search(r'мерител|коктейл|(?:канче|лъжица).*вода|лъжица меламин за черпаци',s):return None,'spoon_type_not_in_template'
  if re.search(r'десерт',s) and 10681 in allowed:return 10681,'specific_dessert_spoon'
  if re.search(r'лъжиц.*чай|чаени.*лъж',s) and 10682 in allowed:return 10682,'specific_teaspoon'
  if re.search(r'решетъч|спагети|салата|тефлон|дървена лъжица',s) and 9999 in allowed:return 9999,'specific_cooking_spoon'
 if cat==10586 and re.search(r'канче.*(?:мраморно|тефлон|алпака)',s):return None,'saucepan_type_not_in_template_match'
 if cat==13031 and re.search(r'магнит|\bсвещ\b|прожектор',s):return None,'decorative_accessory_type_not_in_template'
 if cat is not None:
  # Keep a reviewed specific category; only correct a cleaning-cloth synonym.
  if cat in {11806,11812} and re.search(r'микрофибър',s) and 12906 in allowed:
   return 12906,'expanded_product_type'
  return cat,reason
 if FORBIDDEN_HEAD.search(s):return None,reason
 # A supported, more specific synonym beats the older generic rule.
 candidates=[]
 for n,(c,rx) in enumerate(COMPILED):
  if c not in allowed:continue
  m=rx.search(s)
  if m and not (m.start() and s[m.start()-1].isalpha()):candidates.append((m.start(),n,c))
 if candidates:
  position,_,new=min(candidates);blocked=FORBIDDEN_HEAD.search(s)
  if blocked and blocked.start()<=position:return cat,reason
  # A real tree must not be confused with a small pendant/tree-shaped lamp.
  if new==13001:
   if not re.search(r'изкуствен.*елха|^(?:коледна )?елха.*(?:лукс|стойка)',s):return cat,reason
  if new==11344 and re.search(r'лъжич.*(?:рисуване|пясък)|играчка|кантар|мерител',s):return cat,reason
  if new==54804:
   if re.search(r'ангора|плетен|зимн',s) and 29279 in allowed:return 29279,'specific_womens_knitted_hat'
   if not re.search(r'костюм|карнавал|маскарад',s):return None,'ordinary_hat_is_not_costume_hat'
  if new==10586 and re.search(r'канче.*(?:мраморно|тефлон|дръжка|13 х 7 х 25)',s):return None,'product_type_not_in_template'
  return new,'expanded_product_type'
 return cat,reason
