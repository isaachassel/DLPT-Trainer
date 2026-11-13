"""Original ALES vocabulary dialogues and question keys. No provider calls.

Each row: exact CSV Russian | exact CSV English | spoken form | contextual
answer | three plausible alternatives | comprehension prompt | fresh review
sentence (containing the same spoken form). IDs include both headword and sense.
"""
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from core.ales import ales_id

SPECS = [
('weather', 1, 'Planning an outdoor event', [
('A', 'Ты посмотрел прогноз на завтра? Ожидается похолодание, а к вечеру возможны осадки. Утром ветер будет слабым.'),
('B', 'Тогда встречу лучше провести в помещении. А что будет в воскресенье?'),
('A', 'Обещают переменную облачность. Но прогноз ещё могут изменить, поэтому окончательное решение примем завтра.')], '''
похолодание (холодный 13)|cooling|похолодание|a drop in temperature|a rise in temperature;a change in wind direction;a rise in air pressure|What temperature change is expected tomorrow?|В конце недели начнётся похолодание. Я возьму тёплую куртку.
осадки|precipitation|осадки|precipitation|sunshine;fog;strong wind|What may arrive by evening?|В этом районе осадки бывают даже летом.
переменная облачность|variable cloudiness|переменную облачность|changing cloud cover|continuous clear skies;thick fog throughout the day;continuous heavy rain|What sky conditions are forecast for Sunday?|На завтра обещают переменную облачность, а точную температуру назовут позже.
ожидается (ждать 35)|is expected|Ожидается|is expected|has ended;has been ruled out;has been measured|How does the speaker present tomorrow’s cooling?|Ожидается новая группа посетителей. Подготовьте для них зал.
'''),
('travel', 1, 'Checking a passenger service', [
('A', 'Я уточнил маршрут на завтра. Наш рейс отправляется в девять. Лучше приехать заранее.'),
('B', 'Мы поедем на автобусе или на теплоходе? В расписании не вижу названия транспорта.'),
('A', 'На теплоходе. Друзья пригласили нас на вечернюю встречу, поэтому важно не опоздать. Вечером проверю время отправления.')], '''
маршрут|route, itinerary|маршрут|route|fare;passenger list;luggage allowance|What did the first speaker check for tomorrow?|Маршрут изменили после ремонта дороги.
рейс|flight, trip, run|рейс|scheduled service|ticket office;travel document;waiting room|What leaves at nine?|Этот рейс выполняется только по пятницам.
приглашать/пригласить|to invite|пригласили|invited|warned;thanked;accompanied|What did the friends do regarding the evening meeting?|Нас пригласили на открытие музея.
теплоход|motor ship|теплоходе|motor ship|electric train;coach;passenger aircraft|What vehicle will they travel on?|На теплоходе открыли небольшое кафе.
'''),
('work', 1, 'Discussing a local employment report', [
('A', 'В новом отчёте говорится, что безработица снизилась. Но доход многих семей почти не изменился.'),
('B', 'А на нашем предприятии появились новые места? Я ищу работу с весны.'),
('A', 'Да, сейчас открыта одна должность. Завтра можно позвонить в отдел кадров и узнать подробности.')], '''
безработица|unemployment|безработица|unemployment|inflation;production;education|Which measure decreased in the report?|Безработица остаётся главной темой встречи.
доход|income|доход|income|expenses;savings;debt|What has barely changed for many families?|Мой доход зависит от количества заказов.
предприятие|enterprise, venture|предприятии|enterprise|trade union;employment agency;municipal council|Where does the second speaker ask about jobs?|На предприятии сегодня проводят собрание.
должность|post, position, office|должность|job position|training course;work shift;business contract|What is currently available?|Эта должность требует знания двух языков.
'''),
('budget', 2, 'Revising an operating budget', [
('A', 'После совещания решили снизить расходы на поездки. Стоимость оборудования пока не обсуждали.'),
('B', 'Значит, закупку отменяют?'),
('A', 'Нет. Оборудование закажут в этом месяце. Сначала бухгалтер подготовит новый расчёт, а потом руководитель его подпишет.')], '''
снижать/снизить|to reduce, to decrease|снизить|reduce|increase;postpone;verify|What will they do to travel spending?|Мы решили снизить цену на старую модель.
расходы|expenses|расходы|expenses|revenues;profits;reserves|What will be changed in the travel budget?|Расходы записаны в отдельной таблице.
стоимость (стоить 18)|cost|Стоимость|cost|quality;availability;capacity|Which aspect of the equipment has not yet been discussed?|Стоимость билета зависит от даты поездки.
оборудование|equipment|Оборудование|equipment|raw materials;finished products;office space|What will they order this month?|Оборудование привезут после обеда.
'''),
('diplomacy', 2, 'Preparing a briefing on a meeting', [
('A', 'Переговоры закончились поздно вечером. Представитель делегации сказал, что стороны продолжат работу на следующей неделе.'),
('B', 'А соглашение уже готово?'),
('A', 'Документ ещё обсуждают. В сообщении особо отметили сотрудничество в области науки, но подробностей пока нет.')], '''
переговоры|negotiations, talks|Переговоры|negotiations|elections;celebrations;inspections|What ended late in the evening?|Переговоры начнутся после обеда.
представитель|representative|Представитель|representative|interpreter;opponent;observer|Who gave the statement for the delegation?|Представитель компании ответит на вопросы.
соглашение|agreement|соглашение|agreement|complaint;invitation;budget|What document does the second speaker ask about?|Новое соглашение касается работы музея.
сотрудничество|cooperation|сотрудничество|cooperation|competition;independence;disagreement|What relationship in science was highlighted?|Университет предложил сотрудничество местному музею.
'''),
('research', 2, 'Organizing a research project', [
('A', 'На исследование выделили средства из городского бюджета. Первые данные уже поступили, но их ещё нужно проверить.'),
('B', 'Кто будет готовить итоговый доклад?'),
('A', 'Наша группа. Её основная цель — сравнить результаты за два года. До пятницы нужно составить план работы.')], '''
исследование|research|исследование|research|construction;training;advertising|What activity received funding?|Это исследование займёт несколько месяцев.
выделять/выделить|to allocate, to apportion|выделили|allocated|borrowed;returned;withheld|What did the city do with the project funds?|Для выставки выделили отдельную комнату.
данные|data|данные|data|equipment;instructions;invoices|What has already arrived and needs checking?|Новые данные изменили наше представление о проблеме.
цель|aim, goal|цель|goal|cause;obstacle;expense|How is comparing the two years described?|Наша цель — закончить работу до зимы.
'''),
('elections', 2, 'Following a city campaign', [
('A', 'Выборы назначены на осень. Один кандидат уже начал свою кампанию и вчера встретился с жителями района.'),
('B', 'Какой лозунг он использует? Я видел плакат, но не успел прочитать.'),
('A', 'На нём было написано: «Город для всех». Пока трудно сказать, насколько велика поддержка этого кандидата.')], '''
выборы|elections|Выборы|elections|negotiations;appointments;inspections|What is scheduled for autumn?|Выборы состоятся в следующем месяце.
кампания|campaign|кампанию|campaign|company;coalition;committee|What has the candidate started?|Редакция обсуждает новую кампанию в городе.
лозунг|slogan|лозунг|slogan|signature;address;schedule|What does the second speaker ask about on the poster?|Этот лозунг появился на нескольких плакатах.
поддержка|support|поддержка|support|opposition;experience;responsibility|What is still difficult to gauge about the candidate?|Поддержка жителей помогла сохранить библиотеку.
'''),
('rules', 3, 'Reading a notice about new rules', [
('A', 'Вчера опубликовали новые правила работы центра. Один пункт запрещает проводить мероприятия после десяти вечера.'),
('B', 'Это уже действует? У нас встреча в пятницу.'),
('A', 'Правила вступают в силу в понедельник. В письме также говорится, кто несёт ответственность за их выполнение. Я пришлю тебе полный текст.')], '''
опубликовать|to publish|опубликовали|published|repealed;drafted;translated|What happened to the new rules yesterday?|В газете опубликовали интервью с директором.
запрещать/запретить|to ban, to prohibit|запрещает|prohibits|recommends;permits;requires|What does the rule do regarding late events?|Это правило запрещает оставлять дверь открытой.
вступать в силу|to become effective|вступают в силу|become effective|are discussed;expire;are rewritten|What happens to the rules on Monday?|Новые условия вступают в силу завтра.
ответственность|responsibility|ответственность|responsibility|permission;payment;priority|What does the letter assign for carrying out the rules?|Ответственность за ключи лежит на дежурном.
'''),
('relief', 2, 'Coordinating a relief response', [
('A', 'После землетрясения к нам приехал доброволец из соседнего города. Он предложил помочь в центре, где принимают заявки.'),
('B', 'Что нужно привезти в первую очередь?'),
('A', 'Продовольствие. Сейчас на складе его мало. О разрушениях ещё собирают сведения, поэтому список нуждающихся будут дополнять.')], '''
землетрясение|earthquake|землетрясения|earthquake|flood;storm;fire|Which event prompted the response?|После землетрясения школу временно закрыли.
доброволец|volunteer|доброволец|volunteer|inspector;contractor;journalist|Who offered to help at the center?|Новый доброволец будет работать по субботам.
продовольствие|provisions|Продовольствие|food supplies|building materials;medical equipment;fuel|What is needed first?|Продовольствие доставили на двух машинах.
разрушение|destruction|разрушениях|destruction|recoveries;evacuations;deliveries|What are they still collecting information about?|О разрушениях сообщили в вечернем выпуске.
'''),
('aviation', 3, 'Clarifying an airport update', [
('A', 'В сообщении указано, что взлёт отложили из-за неполадок. Экипаж остаётся на месте и ждёт решения специалистов.'),
('B', 'Пассажирам уже объяснили причину задержки?'),
('A', 'Да, но точное время пока не назвали. Заодно проверят запас горючего. Следующее сообщение обещают через полчаса.')], '''
взлёт|take off|взлёт|takeoff|landing;boarding;inspection|What was postponed?|Сегодня взлёт наблюдали с балкона аэропорта.
неполадки|flaw, defect, trouble|неполадок|technical faults|weather conditions;staff shortages;route changes|What caused the postponement?|Из-за неполадок лифт временно не работает.
экипаж|crew|Экипаж|crew|passengers;ground technicians;airport management|Who is waiting on site for the specialists’ decision?|Экипаж готовится к следующему рейсу.
горючее|fuel|горючего|fuel|drinking water;spare parts;oxygen|Which supply will also be checked?|Запаса горючего хватит на всю поездку.
'''),
('shipping', 3, 'Arranging a delivery by water', [
('A', 'Судно задерживается у входа в пролив. Диспетчер пока не сообщил, когда оно сможет продолжить путь.'),
('B', 'На борту наш товар? Покупатель спрашивает о сроках.'),
('A', 'Да. После прибытия его нужно перевезти на склад. Я предупрежу покупателя и уточню, когда будет свободна машина.')], '''
судно (pl. суда)|ship, vessel|Судно|vessel|train;aircraft;truck|What is delayed?|Судно вышло из порта утром.
пролив|strait, channel|пролив|strait|harbor;canal lock;lake|What water feature is the vessel approaching?|Этот пролив часто упоминают в морских прогнозах.
товар|commodity, merchandise, goods|товар|merchandise|crew;fuel;mail|What is on board for the buyer?|Этот товар привезли из другого города.
перевозить/перевезти (возить 32)|to carry over, to transport|перевезти|transport|inspect;sell;repackage|What must happen to the goods after arrival?|Нужно перевезти столы в соседнее здание.
'''),
('justice', 3, 'Checking a court report', [
('A', 'Суд объявил приговор вчера вечером. В редакции хотят опубликовать короткую заметку, но сначала проверят все формулировки.'),
('B', 'Кто объяснит нам юридические детали?'),
('A', 'Юрист, который следил за делом. В заметке также упомянут расследование, начатое в прошлом году. Пока текст не готов.')], '''
суд|court (of law)|Суд|court|prosecution;police force;prison administration|Which body made yesterday’s announcement?|Суд рассмотрит документы на следующей неделе.
приговор|sentence, verdict|приговор|verdict|charge;appeal;testimony|What did that body announce?|Приговор зачитали после перерыва.
юрист|lawyer|Юрист|lawyer|witness;investigator;juror|Who will explain the legal details?|Юрист попросил прислать копию договора.
расследование|investigation|расследование|investigation|trial;arrest;imprisonment|What began last year and will be mentioned?|Расследование ещё не закончено.
'''),
('science', 2, 'Preparing an exhibition label', [
('A', 'На выставке покажут новое устройство. Его изобретатель приедет в пятницу и ответит на вопросы посетителей.'),
('B', 'Испытание уже закончилось? Нам нужны сведения для стенда.'),
('A', 'Да, вчера. Точный результат сообщат завтра. Пока на стенде будут только название и краткая история проекта.')], '''
устройство|device, mechanism|устройство|device|method;material;building|What will be shown at the exhibition?|Это устройство помогает измерять влажность.
изобретатель|inventor|изобретатель|inventor|buyer;reviewer;supplier|Who will visit on Friday?|Изобретатель рассказал о своей первой работе.
испытание|test|Испытание|test|production;registration;delivery|Which process has finished?|Испытание проведут в другой комнате.
точный|exact, precise|Точный|precise|preliminary;expected;disputed|What kind of result will be announced tomorrow?|Точный адрес указан в приглашении.
'''),
('sport', 1, 'Reviewing a sports bulletin', [
('A', 'Вчера закончилось соревнование. Один легкоатлет получил специальную награду, а имена остальных победителей назовут сегодня.'),
('B', 'Ты видел утреннюю встречу двух команд?'),
('A', 'Только последние минуты. В итоге была ничья. Полную запись обещают показать вечером.')], '''
соревнование|competition|соревнование|competition|training session;selection meeting;opening ceremony|What ended yesterday?|Это соревнование проводят каждый год.
легкоатлет|(track and field) athlete|легкоатлет|track-and-field athlete|swimmer;cyclist;skater|What type of athlete received special recognition?|Этот легкоатлет тренируется в нашем городе.
награда|award|награду|award|invitation;contract;penalty|What did the athlete receive?|Она получила награду за свою работу.
ничья|tie|ничья|a draw|a home-team victory;an away-team victory;a cancellation|How did the two teams’ meeting end?|После трудной игры снова была ничья.
'''),
('press', 3, 'Editing an international news brief', [
('A', 'Источник подтвердил сообщение о встрече. Но редактор просит не указывать её продолжительность: эту деталь ещё проверяют.'),
('B', 'В заметке будет цитата из выступления?'),
('A', 'Да. Гость подчеркнул, что нынешний проект отличается от предыдущего. Остальные подробности появятся в вечернем выпуске.')], '''
источник|source|Источник|source|editor;translator;publisher|Who or what confirmed the report?|Источник этой информации пока не назван.
продолжительность|length|продолжительность|duration|location;purpose;attendance|Which detail should be left out for now?|Продолжительность поездки зависит от погоды.
подчёркивать/подчеркнуть|to underline, to emphasize|подчеркнул|emphasized|denied;doubted;concealed|What did the guest do with the comparison of the projects?|Он подчеркнул важность этой встречи.
нынешний|present|нынешний|current|previous;planned;canceled|Which project is being compared with the earlier one?|Наш нынешний руководитель хорошо знает город.
'''),
]


def build():
    passages = []
    for key, stage, title, turns, lines in SPECS:
        targets = []
        text = '\n'.join(text for _, text in turns)
        for n, line in enumerate(lines.strip().splitlines(), 1):
            ru, en, form, meaning, alternatives, prompt, review = line.split('|')
            # Case may differ between speech and the review sentence.
            pattern = r'(?<!\w)' + re.escape(form) + r'(?!\w)'
            if not re.search(pattern, text, re.I) or not re.search(pattern, review, re.I):
                raise ValueError(f'{key}: target missing: {form}')
            if len(alternatives.split(';')) != 3 or len(set([meaning, *alternatives.split(';')])) != 4:
                raise ValueError('Four distinct options required')
            evidence = next(sentence.strip() for sentence in re.split(r'(?<=[.!?])\s+', text)
                            if re.search(pattern, sentence, re.I))
            targets.append(dict(id=f'ales_{key}_{n}', word_id=ales_id(ru, en), term=ru, sense_hints=[en],
                target=form, meaning=meaning, distractors=alternatives.split(';'), prompt=prompt,
                evidence=evidence, explanation=f'“{form}” means {meaning} in this passage.',
                review_target=form, review_text=review))
        passages.append(dict(id='ales_' + key, title=title, language='ru', stage=stage, collection='ales',
            source='Original ALES study dialogue; provisional language review',
            turns=[dict(speaker=s, text=t) for s, t in turns], targets=targets))
    return dict(version=1, passages=passages)


if __name__ == '__main__':
    path = ROOT / 'data/study/ales/passages.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Built {len(SPECS)} ALES passages.')
