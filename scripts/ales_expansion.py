"""Second ALES batch: 80 previously uncovered senses, with original review contexts.

Schema matches prepare_ales_passages.SPECS. These examples are fictional study
material; no account of real events or instructor validation is claimed.
"""

SPECS = [
('e2_storm', 1, 'Choosing a day for a walk', [
('A', 'Вчера была гроза, и мой рюкзак до сих пор мокрый. Хорошо, что документы лежали в отдельном пакете.'),
('B', 'А завтра можно будет пойти в горы? Внизу сейчас десять градусов тепла.'),
('A', 'Лучше подождать. На вершине обещают снегопад. Я проверю прогноз ещё раз вечером и тогда тебе позвоню.')], '''
гроза|thunderstorm|гроза|a thunderstorm|a snowstorm;a dust storm;a heat wave|What weather occurred yesterday?|Гроза началась, когда мы вышли из магазина.
мокрый|wet|мокрый|wet|torn;dirty;empty|What is the condition of the backpack?|Этот плащ ещё мокрый, его нельзя убирать в шкаф.
градус|degree|градусов|degrees|meters;hours;kilometers|What unit is used in the temperature report?|В комнате около двадцати градусов.
снегопад|snowfall|снегопад|snowfall|rainfall;fog;strong sunshine|What is forecast at the summit?|Из-за того что начался снегопад, мы вернулись домой.
'''),
('e2_museum', 1, 'Arranging a museum visit', [
('A', 'В субботу откроется выставка. Я записал её название, чтобы потом найти информацию на сайте музея.'),
('B', 'Кто будет на открытии?'),
('A', 'Приедет знаменитый фотограф. Мы решили посетить музей утром, пока там не очень много людей. Билеты можно купить у входа.')], '''
выставка|exhibition|выставка|an exhibition|a rehearsal;an auction;a lecture|What opens on Saturday?|Выставка будет работать до конца месяца.
название|name|название|name|address;price;opening time|What did the first speaker write down?|Я забыл название этой книги.
знаменитый|famous|знаменитый|famous|young;local;retired|How is the visiting photographer described?|Этот знаменитый актёр раньше работал учителем.
посещать/посетить|to attend|посетить|visit|avoid;restore;photograph|What have the speakers decided to do regarding the museum?|Мы хотим посетить новую библиотеку.
'''),
('e2_camp', 1, 'Discussing a summer program', [
('A', 'Мой сын этим летом едет в лагерь. Он уже подросток и хочет попробовать что-нибудь новое.'),
('B', 'Кто поедет вместе с ним?'),
('A', 'Его сверстник из соседнего дома. Родителям выдали памятку: там описано, какое поведение ожидается от участников. Вечером мы прочитаем её вместе.')], '''
лагерь|camp|лагерь|a camp|a university;a hospital;a theater|Where is the son going this summer?|Этот лагерь находится у озера.
подросток|teenager|подросток|a teenager|a preschooler;an adult;a college graduate|Which age group does the son belong to?|Подросток спросил, где находится спортивный зал.
сверстник|peer, contemporary|сверстник|someone of his own age|his older cousin;his younger brother;his teacher|What does the description of his companion tell us?|Мой сверстник уже работает в этой компании.
поведение|conduct, behavior|поведение|behavior|clothing;equipment;payment|What expectation does the handout describe?|Его поведение на встрече всех удивило.
'''),
('e2_harbor', 2, 'Checking a coastal travel notice', [
('A', 'Вчера у побережья заметили лодку. По словам наблюдателя, она начала дрейфовать ещё до обеда.'),
('B', 'Это была лодка с нашего острова?'),
('A', 'Пока неизвестно. Радиостанция передала сообщение на материк. Мы ждём уточнений, прежде чем менять планы завтрашней поездки.')], '''
побережье|coast|побережья|the coast|the river mouth;the lake shore;the harbor entrance|Near which geographical feature was the craft seen?|У побережья сегодня сильный ветер.
лодка|boat|лодку|a boat|a ferry;a cargo ship;a raft|What kind of craft did the observer see?|На берегу мы нашли старую лодку.
дрейфовать|to drift|дрейфовать|drift|sink;dock;accelerate|What did the craft begin doing before lunch?|Без ветра льдина продолжала дрейфовать.
материк|mainland|материк|the mainland|the island;the peninsula;the archipelago|Where was the radio message sent?|Завтра мы возвращаемся на материк.
'''),
('e2_factory', 2, 'Preparing a factory work plan', [
('A', 'Завод получил новый заказ. Производство начнут в понедельник, если всё будет готово к концу недели.'),
('B', 'Что поручили нашему участку?'),
('A', 'Нужно изготовить детали по новым чертежам. Кроме того, мастер попросил заменить старый станок. Завтра уточним, когда привезут другой.')], '''
заказ|order|заказ|an order|a complaint;a loan;an inspection notice|What did the factory receive?|Этот заказ нужно выполнить до пятницы.
производство|production|Производство|production|delivery;recruitment;demolition|Which activity is planned to begin on Monday?|Производство временно остановили.
изготовлять/изготовить (готовить 14)|to make, to manufacture|изготовить|manufacture|inspect;pack;repair|What must the section do with the parts?|Мастер обещал изготовить новую раму.
заменять/заменить (менять 35)|to replace|заменить|replace|repair;clean;inspect|What did the foreman request for the old machine?|Нужно заменить лампу в коридоре.
'''),
('e2_market', 3, 'Reading a business column', [
('A', 'В газете пишут, что биржа закончила неделю спокойно. Акция одной компании, однако, заметно изменилась в цене.'),
('B', 'А что говорится о ситуации в целом?'),
('A', 'Автор считает, что рынок пока нестабилен. Он описывает выгодный договор двух фирм, но подчёркивает, что это лишь один пример.')], '''
биржа|stock exchange|биржа|the stock exchange|the central bank;the tax office;the customs office|Which institution is said to have ended the week quietly?|Эта биржа открывается утром.
акция|share, stock|Акция|a share of stock|a sales promotion;a public demonstration;a charitable event|What changed in price in the business report?|Акция этой фирмы стала дешевле.
рынок|market|рынок|the market|the workforce;the budget;the supply chain|What does the author describe as unstable?|Местный рынок постепенно меняется.
выгодный|profitable, advantageous|выгодный|advantageous|temporary;compulsory;disputed|How is the agreement between the firms described?|Это выгодный вариант для небольшой компании.
'''),
('e2_rail', 2, 'Asking about a railway service', [
('A', 'Железная дорога через наш район пока закрыта. Движение остановили в начале недели.'),
('B', 'Когда его собираются возобновить?'),
('A', 'Точный срок ещё не назвали. В кассе посоветовали проверить расписание завтра. До этого времени я не буду покупать билет.')], '''
железная дорога|railroad|Железная дорога|the railway|the highway;the canal;the footpath|Which transport route is closed?|Железная дорога проходит за деревней.
движение|movement; traffic|Движение|traffic|construction;ticket sales;maintenance|What was stopped at the beginning of the week?|Движение на мосту ограничили.
возобновлять/возобновить|to resume, to renew|возобновить|resume|cancel permanently;reroute;reduce|What future action does the second speaker ask about?|Мы хотим возобновить занятия после каникул.
срок|term|срок|time frame|cause;cost;route|Which detail has not been specified yet?|Срок выполнения работы указан в договоре.
'''),
('e2_housing', 1, 'Finding the meeting place', [
('A', 'В приглашении указан жилой дом рядом с площадью. Нас встретят в вестибюле, а потом покажут помещение наверху.'),
('B', 'Это тот небоскрёб, который видно от станции?'),
('A', 'Нет, нам нужен другой дом, расположенный за парком. Я пришлю тебе фотографию входа, чтобы ты не заблудился.')], '''
жилой дом|apartment house|жилой дом|an apartment building|an office building;a hotel;a shopping center|What type of building is named in the invitation?|Этот жилой дом построили недавно.
вестибюль|lobby|вестибюле|the lobby|the basement;the stairwell;the courtyard|Where will the visitors be met?|В вестибюле поставили новые кресла.
небоскрёб|skyscraper|небоскрёб|a skyscraper|a monument;a bridge;a clock tower|What landmark does the second speaker ask about?|Этот небоскрёб виден из нашего окна.
расположенный|located|расположенный|located|planned for construction;recently demolished;advertised for sale|What does the description say about the building behind the park?|Магазин, расположенный у станции, уже закрыт.
'''),
('e2_clinic', 2, 'Preparing a clinic information sheet', [
('A', 'В клинику пришёл донор. Его попросили сначала заполнить анкету, а затем подождать в коридоре.'),
('B', 'О чём говорится в новой памятке?'),
('A', 'Там объясняют, как хранится кровь. Отдельный раздел посвящён лечению. Название заболевания в заголовке написали полностью, без сокращений.')], '''
донор|blood donor|донор|a blood donor|a patient;a surgeon;a visitor|Who arrived at the clinic?|Сегодня донор встретился с врачом.
кровь|blood|кровь|blood|medicine;food;laboratory equipment|What does the handout explain how to store?|В лаборатории проверяют кровь.
лечение (лечить 30)|treatment|лечению|treatment|diagnosis;prevention;rehabilitation|What is the separate section devoted to?|Врач объяснил, как подготовиться к лечению.
заболевание (заболеть 30)|illness, disease|заболевания|disease|medication;procedure;department|What name is written out fully in the heading?|Причину заболевания пока не установили.
'''),
('e2_fire', 2, 'Checking on a neighbor after an incident', [
('A', 'У соседей ночью был пожар. Один человек пострадал, но подробностей пока нет.'),
('B', 'А собаку удалось спасти?'),
('A', 'Да, она сейчас у знакомых. Утром жители решили оказывать помощь семье. Я сначала позвоню и узнаю, что им нужно.')], '''
пожар|fire|пожар|a fire|a burglary;a flood;a power outage|What happened at the neighbors’ home?|Пожар заметили из окна соседнего дома.
пострадать|to suffer, to be injured|пострадал|was injured|was rescued;was questioned;was evacuated|What is reported about one person?|Водитель пострадал во время аварии.
спасать/спасти|to save, to rescue|спасти|rescue|find;feed;identify|What outcome does the second speaker ask about for the dog?|Люди смогли спасти старые фотографии.
оказывать помощь|to help, to assist|оказывать помощь|provide assistance|request compensation;assign blame;collect testimony|What did residents decide to do for the family?|Студенты будут оказывать помощь посетителям музея.
'''),
('e2_roads', 1, 'Changing a driving plan', [
('A', 'По радио сообщили, что на шоссе произошла авария. Одна полоса закрыта, поэтому мы можем задержаться.'),
('B', 'Может быть, поедем через деревню?'),
('A', 'Да, но там ограничена скорость. Давай выедем пораньше и предупредим друзей, что точное время приезда пока неизвестно.')], '''
шоссе|highway|шоссе|the highway|the railway;the bridge;the parking lot|Where did the reported event occur?|Это шоссе ведёт к границе.
авария|accident, crash|авария|an accident|a demonstration;a road inspection;a repair project|What happened on the road?|Авария произошла рано утром.
полоса|strip, lane|полоса|a lane|an exit;a tunnel;a junction|Which part of the road is closed?|Правая полоса сегодня свободна.
скорость|speed|скорость|speed|vehicle weight;vehicle height;parking time|What is restricted in the village?|Скорость нужно уменьшить перед поворотом.
'''),
('e2_airport', 3, 'Clarifying an aviation bulletin', [
('A', 'В сводке говорится, что самолёт совершил аварийную посадку. Причина пока не установлена.'),
('B', 'Что будет дальше?'),
('A', 'Специалисты проверят безопасность дальнейшего полёта. Во время первого осмотра они обнаружили повреждение, но в сообщении не уточняется, где именно.')], '''
аварийная посадка|emergency landing|аварийную посадку|an emergency landing|a routine landing;a test flight;a canceled takeoff|What maneuver did the aircraft make?|Пилот готовился выполнить аварийную посадку.
причина|reason, cause|Причина|the cause|the location;the time;the aircraft type|What remains undetermined?|Причина задержки указана в письме.
безопасность|safety, security|безопасность|safety|cost;duration;purpose|What aspect of a further flight will specialists check?|Безопасность посетителей обсуждали на собрании.
обнаруживать/обнаружить|to discover, to find, to detect|обнаружили|discovered|repaired;caused;concealed|What did the specialists do regarding the damage?|В архиве обнаружили старую карту.
'''),
('e2_environment', 3, 'Discussing an environmental survey', [
('A', 'В пробе нашли нефть. Эксперт назвал участок опасным, но окончательный отчёт ещё не готов.'),
('B', 'Уже известно, какой вред нанесён берегу?'),
('A', 'Пока нет. На встрече предложили одну меру, которую обсудят завтра. До этого мы не будем менять текст объявления.')], '''
нефть|crude oil|нефть|crude oil|gasoline;diesel fuel;lubricating oil|What substance was found in the sample?|В этом районе добывают нефть.
опасный|dangerous|опасным|dangerous|inaccessible;protected;uninhabited|How did the expert describe the area?|Этот путь считают опасным зимой.
вред|harm|вред|harm|benefit;value;attention|What effect on the shore does the second speaker ask about?|Старые трубы могут причинить вред зданию.
мера|measure|меру|a measure to take|a unit of length;a measurement result;a survey boundary|What was proposed for discussion tomorrow?|Комиссия предложила новую меру для решения проблемы.
'''),
('e2_education', 2, 'Preparing a public discussion', [
('A', 'Тема следующей встречи — образование. Организаторы хотят узнать, как общество относится к новым предложениям.'),
('B', 'У школьников будет возможность выступить?'),
('A', 'Да, их тоже пригласили. Дискуссию проведёт независимый эксперт. После встречи участникам пришлют краткий отчёт.')], '''
образование|education|образование|education|employment;healthcare;housing|What is the topic of the next meeting?|Образование обсуждают в новом выпуске журнала.
общество|society|общество|society|the government;the school staff;the student council|Whose response to the proposals interests the organizers?|Общество постепенно меняет отношение к этой проблеме.
возможность|possibility|возможность|an opportunity|an obligation;a restriction;a reason|What does the second speaker ask whether pupils will have?|У нас появилась возможность увидеть архив.
независимый (зависеть 43)|independent|независимый|independent|government-appointed;inexperienced;foreign|How is the expert leading the discussion described?|Независимый наблюдатель подготовил свой отчёт.
'''),
('e2_policy', 3, 'Dividing topics for a seminar', [
('A', 'Правительство опубликовало большой доклад. Я читаю раздел, посвящённый внешней политике.'),
('B', 'А кто подготовит сообщение о внутренней политике?'),
('A', 'Это поручили Ирине. В конце мы сравним, как государство представлено в разных разделах. Цитаты нужно выписать заранее.')], '''
правительство|government|Правительство|the government|the parliament;the opposition;the court|Who published the report?|Правительство обсудит этот вопрос завтра.
внешняя политика|foreign policy|внешней политике|foreign policy|domestic policy;economic policy;environmental policy|Which policy area is the first speaker reading about?|В статье говорится о внешней политике страны.
внутренняя политика|internal (domestic) policy|внутренней политике|domestic policy|foreign policy;defense policy;trade policy|Which policy area will Irina cover?|Мы готовим доклад о внутренней политике.
государство|state, country|государство|the state|the political party;the delegation;the ministry|What entity will they compare across sections?|Это государство недавно открыло новое посольство.
'''),
('e2_council', 3, 'Summarizing a council discussion', [
('A', 'На заседании решили обсудить новый закон. Несколько участников попросили дополнительное время.'),
('B', 'А что сказал председатель?'),
('A', 'Он высказал своё мнение, но отказался отвечать на последний вопрос. В протоколе это тоже отметили. Полный текст заседания появится позже.')], '''
обсуждать/обсудить|to discuss|обсудить|discuss|adopt;repeal;enforce|What action did the participants decide to take at the meeting?|Мы хотим обсудить план поездки.
закон|law|закон|law|budget;report;contract|What was the subject of the planned discussion?|Этот закон приняли несколько лет назад.
мнение|opinion|мнение|opinion|decision;promise;demand|What did the chair express?|Моё мнение по этому вопросу изменилось.
отказываться/отказаться|to refuse|отказался|refused|agreed;forgot;hurried|How did the chair respond to the final question?|Он отказался подписывать документ без проверки.
'''),
('e2_conference', 2, 'Planning a joint conference', [
('A', 'Мне пришло приглашение на конференцию. Это совместный проект двух университетов.'),
('B', 'Ты сможешь присутствовать на открытии?'),
('A', 'Да. Моё выступление назначено на второй день, поэтому утром я свободен. Потом останусь послушать остальных участников.')], '''
приглашение|invitation|приглашение|an invitation|an invoice;a complaint;a reminder|What did the speaker receive?|Приглашение лежит на столе.
совместный|joint|совместный|joint|competitive;temporary;commercial|How is the universities’ project described?|Мы готовим совместный доклад.
присутствовать|to be present|присутствовать|be present|speak;organize;translate|What does the second speaker ask about the opening?|Я не смогу присутствовать на собрании.
выступление|speech|выступление|speech|arrival;interview;rehearsal|What is scheduled for the second day?|Его выступление началось после перерыва.
'''),
('e2_expedition', 2, 'Preparing field observations', [
('A', 'Наша группа едет в пустыню. Базу устроят у подножия горы, но точное место ещё выбирают.'),
('B', 'Большое расстояние от базы до станции?'),
('A', 'Это уточним завтра. Мы будем наблюдать за животными и каждый вечер записывать результаты. Карты уже подготовлены.')], '''
пустыня|desert|пустыню|the desert|the forest;the marsh;the tundra|What environment is the group traveling to?|Учёные собираются исследовать эту пустыню.
подножие|foot (of a mountain)|подножия|the foot|the summit;the ridge;the far side|Where in relation to the mountain will the base be?|У подножия холма стоит маленький дом.
расстояние|distance|расстояние|distance|travel time;difference in altitude;route difficulty|Which measurement between the base and station is asked about?|Расстояние между домами измерили утром.
наблюдать|to observe|наблюдать|observe|capture;feed;transport|What will the group do regarding the animals?|Из окна удобно наблюдать за птицами.
'''),
('e2_memories', 2, 'Preparing a community interview', [
('A', 'Сегодня в школу придёт полковник в отставке. Он расскажет о людях, с которыми работал много лет назад.'),
('B', 'Почему организаторы выбрали именно его?'),
('A', 'Он хорошо помнит то время. Для него память о коллегах очень важна. Он говорит, что молодое поколение может гордиться их работой.')], '''
полковник в отставке|retired colonel|полковник в отставке|a retired colonel|a serving colonel;a colonel awaiting promotion;a colonel on temporary leave|Who will visit the school?|Полковник в отставке написал книгу.
память|memory|память|memory|opinion;knowledge;concern|What does the speaker say is important to the visitor regarding colleagues?|Эта фотография — память о нашей поездке.
поколение|generation|поколение|generation|delegation;department;team|Which group of young people is referred to collectively?|Новое поколение выросло в других условиях.
гордиться|to be proud|гордиться|be proud of|be surprised by;be concerned about;be doubtful about|What attitude toward the colleagues’ work does the visitor suggest?|Родители могут гордиться её успехами.
'''),
('e2_broadcast', 3, 'Revising a news segment', [
('A', 'В редакцию поступило сообщение о встрече. Первоначально мы собирались передать его в утреннем выпуске.'),
('B', 'Почему решили подождать?'),
('A', 'Нужен подробный текст, а не только несколько строк. Автор обещал прислать дополнение после обеда. Тогда и решим, что оставить в программе.')], '''
сообщение|report|сообщение|a report|an invitation;a complaint;a payment request|What arrived at the newsroom?|Это сообщение появилось на сайте вечером.
первоначально|initially|Первоначально|initially|eventually;immediately;repeatedly|When in the planning process was the morning slot intended?|Первоначально мы хотели остаться на неделю.
передавать/передать|to broadcast, to transmit|передать|broadcast|translate;verify;archive|What had the newsroom planned to do with the report?|Радиостанция должна передать интервью вечером.
подробный|detailed|подробный|detailed|anonymous;official;short|What kind of text does the editor want?|Мне нужен подробный план здания.
'''),
]
