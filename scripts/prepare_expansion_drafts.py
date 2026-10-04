"""Original Russian practice bank expansion. Offline authoring; never spends credits.

Builds drafts with provisional difficulty rationales, balanced answer keys, and
exact evidence spans. These are original fictional scenarios, not official items.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.constants import ILR_THETA
from core.models import GenerationMetadata, PassageItem, QuestionItem
from core.preset_bank import ContentItem, ContentPackage, ROOT, Turn, write_package
from core.validation import content_hash, target_unit_count, validate_passage, validate_question

# Questions: stem, correct answer first plus three distractors, exact evidence,
# rationale, competency. The materializer rotates keys across the complete set.
def q(stem, answers, evidence, rationale, kind="prominent detail"):
    return (stem, answers, evidence, rationale, kind)


READING = [
    ("0", "Public services", "signage", "Read two labels at a building.",
     "ВХОД. ВЫХОД.", "Floor recognition probe: isolated high-frequency signs, not connected comprehension.", [
         q("What does the first label indicate?", ["Entrance", "Kitchen", "Parking", "Office"], "ВХОД", "The first label identifies an entrance."),
         q("What does the second label indicate?", ["Exit", "Elevator", "Reception", "Toilets"], "ВЫХОД", "The second label identifies an exit.")]),
    ("0", "Commerce", "labels", "Read two labels on a menu.",
     "ЧАЙ. КОФЕ.", "Floor recognition probe: two familiar beverage words.", [
         q("Which drink is listed first?", ["Tea", "Juice", "Water", "Milk"], "ЧАЙ", "The first word means tea."),
         q("Which drink is listed second?", ["Coffee", "Lemonade", "Cocoa", "Kefir"], "КОФЕ", "The second word means coffee.")]),
    ("0+", "Daily life", "notice", "Read a short printed notice.",
     "Библиотека. Открыто: понедельник — пятница. Девять утра — шесть вечера. Суббота, воскресенье: закрыто.",
     "Formulaic opening-hours vocabulary and recognition of days and times.", [
         q("What time does this place open?", ["Nine in the morning", "Six in the morning", "Eight in the evening", "Ten in the evening"], "Девять утра", "The notice gives nine in the morning as its opening time."),
         q("On which day is it closed?", ["Sunday", "Tuesday", "Thursday", "Monday"], "Суббота, воскресенье: закрыто", "Sunday is one of the two days explicitly marked closed.")]),
    ("0+", "Commerce", "advertisement", "Read a short advertisement.",
     "Комната. Улица Лесная, дом восемь. Второй этаж. Рядом метро. Телефон: пять — семь — три.",
     "Formulaic accommodation listing with isolated location details.", [
         q("What is being advertised?", ["A room", "A bicycle", "A garage", "A television"], "Комната", "The heading offers a room."),
         q("What is nearby?", ["The metro", "A stadium", "The airport", "A beach"], "Рядом метро", "The listing explicitly says the metro is nearby.")]),
    ("1", "Daily life", "personal note", "Read a message left at home.",
     "Лена, я сегодня работаю до семи. Ужин на кухне, в большой кастрюле. Хлеб лежит в пакете на столе. Пожалуйста, покорми кошку в шесть. Её еда в маленьком шкафу у окна. Я куплю молоко по дороге домой. Миша.",
     "Connected simple sentences about familiar household actions; explicitly stated details.", [
         q("What does Misha ask Lena to do?", ["Feed the cat", "Buy some milk", "Cook a meal", "Open the window"], "Пожалуйста, покорми кошку в шесть", "Feeding the cat is the direct request addressed to Lena."),
         q("Where is the cat's food?", ["In a small cupboard", "In the large pot", "In the shopping bag", "On the kitchen table"], "Её еда в маленьком шкафу у окна", "The pronoun refers to the cat, whose food is in the cupboard by the window.")]),
    ("1", "Transportation", "service notice", "Read a notice for passengers.",
     "Сегодня автобус номер четыре не останавливается у школы. Идите к аптеке на улице Мира. Новая остановка перед аптекой. Автобус ходит каждые двадцать минут. Билеты можно купить у водителя. Завтра автобус снова будет останавливаться у школы.",
     "Simple directions and a temporary change expressed in common vocabulary.", [
         q("Where should passengers wait today?", ["In front of the pharmacy", "Behind the school", "Beside the station", "Across from the market"], "Новая остановка перед аптекой", "The temporary stop is explicitly located in front of the pharmacy."),
         q("When will the school stop be used again?", ["Tomorrow", "This evening", "Next Monday", "Next month"], "Завтра автобус снова будет останавливаться у школы", "The normal stop returns tomorrow.")]),
    ("1+", "Workplace", "email", "Read an email about a group activity.",
     "Коллеги! Встреча с новыми сотрудниками состоится в четверг, а не в среду, как мы писали раньше. В среду в нашем кабинете будут менять окна. Начало встречи остаётся прежним — в десять утра. Сначала руководитель расскажет о работе отдела, затем мы покажем гостям здание. Обед заказывать не нужно: после экскурсии все пойдут в столовую. Если вы работаете дома, можно подключиться к первой части встречи по ссылке в календаре. Экскурсию по интернету показывать не будем.",
     "Routine work message with a revised schedule, sequence and explicit participation restriction.", [
         q("Why was the meeting moved?", ["Windows will be replaced", "The manager will travel", "The cafeteria will close", "New staff will arrive late"], "В среду в нашем кабинете будут менять окна", "Building work in the office explains the change of day.", "cause and effect"),
         q("Which part can remote workers attend online?", ["The manager's opening talk", "The tour of the building", "The meal in the cafeteria", "The window installation"], "можно подключиться к первой части встречи", "The opening talk comes first, and the email excludes online coverage of the tour.", "sequence")]),
    ("1+", "Education", "course announcement", "Read an announcement about a course.",
     "В районном центре начинается курс фотографии для взрослых. Первое занятие пройдёт в помещении, остальные — на улице, если не будет сильного дождя. Дорогой фотоаппарат не нужен: преподаватель покажет, как снимать на обычный телефон. Курс рассчитан на тех, кто раньше не учился фотографии. Запись заканчивается в пятницу. После записи участники получат письмо с адресом первого занятия. Оплачивать курс до получения письма не надо. Тем, кто не сможет прийти на первое занятие, предложат другую группу в следующем месяце.",
     "Routine instructions with conditions and ordered actions beyond a basic transaction.", [
         q("Who is the course designed for?", ["Adults without photography training", "Professional wedding photographers", "Children with expensive cameras", "Teachers preparing a lecture"], "кто раньше не учился фотографии", "The announcement explicitly targets people with no prior photography study."),
         q("What should an applicant wait for before paying?", ["An email with the location", "The first outdoor lesson", "A call from another student", "The following month's schedule"], "Оплачивать курс до получения письма не надо", "Payment is to follow receipt of the email containing the address.", "sequence")]),
    ("2", "Public services", "local news", "Read a report about a municipal project.",
     "После трёхмесячного ремонта городской бассейн вновь открылся для посетителей. Во время работ заменили систему очистки воды и установили подъёмник для людей, которым трудно пользоваться лестницей. Первоначально открытие планировали на начало сентября, однако поставщик задержал доставку оборудования, и сроки пришлось перенести.\n\nТеперь по будням бассейн начинает работу на час раньше. Утренние часы предназначены для свободного плавания, а после обеда дорожки будут по очереди занимать школьные группы. Абонементы, срок действия которых закончился во время ремонта, продлят на число дней вынужденного перерыва. Для этого владельцам нужно обратиться в кассу с прежним абонементом. Администрация сообщила, что цены пока сохранятся. Вопрос о дополнительных вечерних занятиях решат после первого месяца работы, когда станет ясно, сколько посетителей приходит в это время.",
     "Factual public report across past and future timeframes; cause, procedure and planned decision.", [
         q("What delayed reopening?", ["Late delivery of equipment", "A shortage of swimming instructors", "An increase in ticket prices", "A dispute about school access"], "поставщик задержал доставку оборудования", "A supplier's late delivery caused the schedule change.", "cause and effect"),
         q("How can affected pass holders recover lost access time?", ["Bring their old pass to the cashier", "Apply for a new school membership", "Attend an evening class without booking", "Ask their employer to buy a pass"], "обратиться в кассу с прежним абонементом", "The notice directs them to the cashier with their existing pass."),
         q("What will inform the decision about evening classes?", ["Attendance during the first month", "The supplier's next delivery date", "The number of new school groups", "The cost of the completed repairs"], "когда станет ясно, сколько посетителей приходит в это время", "Management will use observed evening demand before deciding.")]),
    ("2", "Environment", "project report", "Read a report about a neighborhood program.",
     "В двух кварталах района завершился пробный сбор пищевых отходов. На первом этапе контейнеры поставили только у домов, где жители заранее согласились участвовать. Каждой семье выдали памятку с перечнем подходящих отходов. В первые недели в контейнеры часто попадали пластиковые пакеты, поэтому организаторы провели дополнительные встречи и заменили объявления на крышках более понятными.\n\nПо итогам трёх месяцев количество постороннего мусора заметно сократилось. При этом вывоз оказался дороже расчётного: машина приезжала по расписанию даже тогда, когда контейнеры были почти пустыми. Теперь её маршрут будут составлять по сообщениям дворников о заполнении ёмкостей. Расширять программу на весь район пока не собираются. Сначала организаторы проверят, позволит ли новый порядок уменьшить расходы без неприятного запаха во дворах. Результаты следующего этапа обещают обсудить с жителями на открытой встрече.",
     "Concrete factual report explaining a trial, corrective actions and a conditional next step.", [
         q("What initial problem led to additional meetings?", ["Unsuitable material entered the containers", "Residents objected to the meeting location", "Collection vehicles damaged the pavement", "Families could not obtain the printed guide"], "в контейнеры часто попадали пластиковые пакеты", "Plastic bags were contaminating the food-waste collection.", "cause and effect"),
         q("What change is intended to reduce collection costs?", ["Scheduling trips according to container fill", "Replacing caretakers with paid consultants", "Moving containers to every nearby district", "Reducing the number of participating families"], "маршрут будут составлять по сообщениям дворников о заполнении", "Reports of how full containers are will guide routing."),
         q("Why is district-wide expansion being postponed?", ["The revised process needs another trial", "The project has permanently lost funding", "Residents have rejected food-waste collection", "The city has prohibited public meetings"], "Сначала организаторы проверят, позволит ли новый порядок уменьшить расходы", "Organizers will first test whether the revised process controls costs and odor.", "main idea")]),
    ("2+", "Workplace", "analysis", "Read an article discussing a workplace experiment.",
     "Компания сократила число обязательных совещаний и предложила сотрудникам решать текущие вопросы письменно. Через два месяца руководители отчитались об экономии времени: календарь каждого отдела стал заметно свободнее. Однако сами сотрудники оценили перемены неодинаково. Опытные специалисты быстрее выполняли знакомые задачи, тогда как новички иногда ждали ответа на короткий вопрос до конца рабочего дня.\n\nАвторы внутреннего исследования предупреждают, что пустое место в календаре ещё не означает роста производительности. Часть обсуждений просто переместилась в личные переписки, которые не попали в отчёт. Кроме того, при подсчёте учитывали продолжительность встреч, но не время, потраченное на исправление ошибок после неясных письменных указаний.\n\nЭто не повод возвращать все прежние совещания, считают исследователи. Они предлагают различать передачу готовой информации и совместный поиск решения. Первую задачу часто можно выполнить письменно; для второй полезнее короткий разговор с заранее определённой целью. На следующем этапе компания сохранит свободный формат для опытных команд, а новым сотрудникам выделит время для вопросов наставнику. Успех будут оценивать не по числу отменённых встреч, а по срокам выполнения задач и качеству результата.",
     "Interprets a concrete policy using qualifications and competing evidence; partial inference and argument structure.", [
         q("What weakness do researchers identify in the time-saving claim?", ["It omits work displaced into other channels", "It counts breaks as formal meeting time", "It compares employees in different countries", "It assumes that every worker is newly hired"], "Часть обсуждений просто переместилась в личные переписки", "Uncounted messages and rework undermine the claimed saving.", "relationship of ideas"),
         q("What policy do the researchers favor?", ["Match communication format to the task", "Restore the former meeting schedule", "Require written discussion for every issue", "Allow only senior staff to ask questions"], "различать передачу готовой информации и совместный поиск решения", "They distinguish information transfer from collaborative problem solving.", "main idea"),
         q("Why will newcomers receive scheduled access to a mentor?", ["They need timely clarification of unfamiliar work", "They must learn to host long departmental meetings", "They prefer fewer opportunities to discuss tasks", "They are responsible for writing the research report"], "новички иногда ждали ответа на короткий вопрос до конца рабочего дня", "The planned access addresses delays in getting basic questions answered.", "inference")]),
    ("2+", "Culture and society", "commentary", "Read a commentary on a cultural project.",
     "После перевода части музейной коллекции в цифровой формат число посещений сайта резко выросло. В годовом отчёте этот показатель назвали доказательством расширения доступа к культуре. Спорить с удобством нового сервиса трудно: жители других городов теперь могут рассмотреть предметы, ради которых раньше пришлось бы ехать в музей. Но считать каждое открытие страницы полноценной встречей с искусством было бы поспешно.\n\nСтатистика объединяет школьника, изучающего один экспонат целый вечер, и случайного посетителя, закрывшего страницу через несколько секунд. Она почти ничего не говорит и о тех, кто не воспользовался сервисом из-за медленного интернета или неудобного интерфейса. Получается, что хорошо видимая аудитория заслоняет менее заметные группы.\n\nСотрудники музея предлагают дополнить подсчёт просмотров интервью с учителями и посетителями, а также проверить сайт вместе с людьми, которым трудно читать мелкий текст. Эти меры не дадут столь эффектной цифры для отчёта, зато помогут понять, что именно следует изменить. Цифровая коллекция от этого не становится менее ценной. Просто её общественную пользу стоит оценивать по тому, какие возможности появились у разных людей, а не только по общему потоку кликов.",
     "Accessible evaluative prose with a qualified conclusion, contrast and implicit limits of a metric.", [
         q("What is the writer's principal objection to the report?", ["It treats page visits as sufficient evidence of access", "It ignores the cost of transporting physical exhibits", "It assumes online collections reduce classroom learning", "It denies that remote visitors can inspect objects"], "считать каждое открытие страницы полноценной встречей с искусством было бы поспешно", "The writer challenges the interpretation of traffic, not the existence of a benefit.", "main idea"),
         q("Why does the writer mention people with slow internet?", ["To identify people missing from the success measure", "To recommend closing physical museum exhibitions", "To explain why teachers avoid cultural interviews", "To argue that visitor numbers were intentionally forged"], "о тех, кто не воспользовался сервисом из-за медленного интернета", "Nonusers excluded by barriers are invisible in usage totals.", "speaker/writer intent"),
         q("How would the proposed interviews improve evaluation?", ["By showing what different visitors can actually do", "By replacing school visits with advertising surveys", "By making page counts easier to collect each day", "By preventing visitors from leaving negative comments"], "какие возможности появились у разных людей", "The proposed evaluation examines meaningful opportunities for different groups.", "inference")]),
    ("3", "Government and politics", "editorial", "Read an editorial about decision-making in a fictional city.",
     "Городской совет объявил конкурс инициатив, обещая передать жителям право выбирать, на что потратить часть бюджета. На первый взгляд всё устроено безупречно: предложения публикуются, голосование открыто, победителем становится проект, набравший больше голосов. Однако прозрачность последнего шага ещё не делает прозрачным весь путь к нему. Прежде чем инициатива появится на сайте, комиссия оценивает её техническую реализуемость. Именно здесь решается, какие варианты граждане вообще смогут сравнить.\n\nТакая проверка необходима: нельзя голосованием отменить требования безопасности или превратить пожелание в готовый проект. Проблема возникает, когда мотивы отказа остаются внутри комиссии. Тогда административное суждение, возможно вполне обоснованное, воспринимается как произвол, а публичное голосование лишь придаёт уже отфильтрованному выбору вид всеобщего согласия.\n\nЗащитники нынешнего порядка опасаются, что подробное объяснение каждого отказа затормозит конкурс. Это серьёзное возражение, если от комиссии требуют переписки без конца. Но из него не следует, что единственная альтернатива бюрократической перегрузке — молчание. Опубликованные критерии и короткое обоснование позволили бы авторам исправлять проекты, не начиная каждый раз с нуля.\n\nРазумеется, такой порядок не устранит конфликтов интересов. Более того, вначале жалоб может стать больше: люди получат язык, на котором можно оспаривать решения. Принимать этот рост за провал было бы ошибкой. Участие проявляется не только в согласии с победителем, но и в возможности понять собственное поражение. Иначе городу достанется витрина участия, за которой правила по-прежнему определяются без участников.",
     "Supported opinion with concession, hypothesis, metaphor and an implicit distinction between visible procedure and substantive participation.", [
         q("What assumption about transparent voting does the author challenge?", ["That it makes earlier screening decisions transparent too", "That residents can compare projects posted on a website", "That technical review can uncover safety problems", "That a winning project must receive public funding"], "прозрачность последнего шага ещё не делает прозрачным весь путь к нему", "The author distinguishes the visible vote from less visible control of eligible options.", "inference"),
         q("What role does the discussion of administrative workload play?", ["It concedes a concern while rejecting an all-or-nothing response", "It proves that every rejected project deserves public funding", "It dismisses the need for technical expertise in city projects", "It establishes that residents deliberately overwhelm officials"], "единственная альтернатива бюрократической перегрузке — молчание", "The author accepts the workload concern but argues that concise explanations offer a middle course.", "relationship of ideas"),
         q("Why might an initial increase in complaints be compatible with success?", ["Residents may have gained a usable basis for challenging decisions", "Officials may have removed technical review from the competition", "Unsuccessful applicants may have stopped caring about the outcome", "The council may have increased the money assigned to every proposal"], "люди получат язык, на котором можно оспаривать решения", "More informed objections can indicate improved participation rather than deterioration.", "inference")]),
    ("3", "Science and technology", "opinion essay", "Read an essay about institutional use of forecasts.",
     "Когда организация внедряет систему прогнозирования, от неё нередко ждут избавления от неопределённости. Между тем даже точный прогноз не отменяет выбора: он лишь меняет условия, в которых этот выбор совершается. Если модель предсказывает низкий спрос на услугу, руководитель может сократить её доступность. Последующее снижение обращений будет выглядеть подтверждением расчёта, хотя отчасти окажется результатом самого решения.\n\nИз этого не следует, что прогнозы бесполезны. Без них учреждения тоже действуют на основании предположений, только менее явных. Преимущество формальной модели состоит как раз в возможности обсуждать её допущения. Оно исчезает, когда числовой результат превращают в последнюю инстанцию, а ответственность за решение незаметно передают инструменту.\n\nОсобенно соблазнительно такое перемещение ответственности там, где ресурсы ограничены. Ссылка на алгоритм позволяет представить спорный приоритет как техническую необходимость. При этом выбор данных, периода наблюдения и допустимой ошибки уже содержит суждения о том, чьи потери существеннее. Их нельзя проверить одним показателем точности. Модель может одинаково хорошо предсказывать общую нагрузку и систематически недооценивать потребности небольшой группы, которая редко обращалась за помощью прежде.\n\nПоэтому разумная проверка должна включать не только сопоставление прогноза с результатом, но и вопрос о том, как решение изменило саму наблюдаемую ситуацию. Полезно заранее определить условия пересмотра и сохранить возможность действовать вопреки рекомендации. Это не уступка недоверию к вычислениям, а способ не позволить хорошему инструменту стать плохим оправданием. Уверенность здесь заслуживает не тот, кто обещает исключить ошибку, а тот, кто умеет обнаружить её и объяснить, кто отвечает за исправление.",
     "Abstract professional argument with a feedback-loop hypothesis, qualified support and implied institutional incentives.", [
         q("What problem does the opening example illustrate?", ["A decision can help produce the outcome used to validate its forecast", "A forecast can eliminate the need to observe actual service demand", "A service reduction necessarily reveals deliberate statistical fraud", "A low-demand prediction always indicates poor model accuracy"], "отчасти окажется результатом самого решения", "Reduced access can itself reduce requests, so the apparent confirmation is not independent of the intervention.", "inference"),
         q("What is the author's position on formal forecasting models?", ["They are useful when assumptions and responsibility remain open to scrutiny", "They should replace managerial judgment whenever resources are limited", "They are less useful than leaving organizational assumptions unstated", "They should be rejected unless every small group's demand is identical"], "возможности обсуждать её допущения", "The author values explicit assumptions but rejects treating a forecast as the final authority.", "tone or attitude"),
         q("What does the phrase about a tool becoming an excuse imply?", ["Technical recommendations can be used to evade accountability for priorities", "Statistical tools are intended to delay the delivery of public services", "Employees should conceal prediction errors to preserve public confidence", "Improving numerical accuracy removes the need to justify resource decisions"], "ответственность за решение незаметно передают инструменту", "The concern is displacement of responsibility onto a tool that embodies prior human choices.", "meaning from context")]),
]

LISTENING = [
    ("0", "Daily life", "word exchange", "Listen to two speakers naming objects.",
     ["Стол.", "Стул."], "Floor recognition probes: isolated common nouns rather than connected discourse.", [
         q("What does the first speaker name?", ["A table", "A window", "A door", "A shelf"], "Стол", "The first speaker says the word for table."),
         q("What does the second speaker name?", ["A chair", "A bed", "A lamp", "A mirror"], "Стул", "The second speaker says the word for chair.")]),
    ("0", "Daily life", "word exchange", "Listen to two speakers naming colors.",
     ["Белый.", "Чёрный."], "Floor recognition probes: two isolated color words, not a proficiency claim.", [
         q("Which color does the first speaker name?", ["White", "Green", "Yellow", "Red"], "Белый", "The first color word means white."),
         q("Which color does the second speaker name?", ["Black", "Blue", "Orange", "Brown"], "Чёрный", "The second color word means black.")]),
    ("1", "Commerce", "dialogue", "Listen to a customer and an employee.", [
        "Здравствуйте. Мне нужны два билета на вечерний поезд.",
        "На сегодня? Поезд отправляется в восемь.",
        "Да, на сегодня. Мы хотим сидеть рядом.",
        "Есть два места у окна. Оплатить можно картой.",
        "Хорошо. С какой платформы поезд?",
        "С третьей. Платформа за этим зданием."],
     "Simple transaction with explicit time, quantity and location information.", [
         q("What does the customer want?", ["Two tickets for this evening", "One ticket for tomorrow morning", "Three tickets for next week", "A refund for yesterday's trip"], "Мне нужны два билета на вечерний поезд", "The request is for two evening-train tickets, confirmed for today."),
         q("Where does the train depart from?", ["Platform three", "Platform one", "Platform four", "Platform two"], "С третьей", "The employee names the third platform.")]),
    ("1", "Daily life", "dialogue", "Listen to two neighbors talking.", [
        "Вы недавно переехали в наш дом?",
        "Да, в понедельник. Я живу на пятом этаже.",
        "Добро пожаловать! Рядом есть хороший магазин.",
        "Спасибо. А где можно погулять с собакой?",
        "За домом есть маленький парк. Я хожу туда утром.",
        "Отлично, я тоже люблю гулять утром."],
     "Short connected exchange about immediate surroundings; common vocabulary and literal details.", [
         q("When did the new neighbor move in?", ["On Monday", "On Thursday", "On Saturday", "On Sunday"], "Да, в понедельник", "The neighbor explicitly gives Monday as the moving day."),
         q("Where is a place to walk the dog?", ["In the park behind the building", "On the fifth floor of the building", "In the shop across the street", "On the station platform nearby"], "За домом есть маленький парк", "The suggested park is behind the building.")]),
    ("1+", "Education", "dialogue", "Listen to a student asking about an activity.", [
        "Я записалась на экскурсию в пятницу. Мы встречаемся у музея?",
        "Раньше так планировали, но теперь автобус заберёт нас у колледжа. У музея ремонтируют дорогу.",
        "А время изменилось?",
        "Нет, выезжаем в девять. Пожалуйста, приходите минут на десять раньше.",
        "Нужно взять с собой обед?",
        "Да, кафе в музее закрыто. После экскурсии поедим в парке, а в колледж вернёмся к трём."],
     "Routine message with a changed plan and a sequence of explicitly stated events.", [
         q("Why has the meeting point changed?", ["The road near the museum is being repaired", "The college cafeteria is being enlarged", "The group has requested an earlier meal", "The bus cannot arrive before the afternoon"], "У музея ремонтируют дорогу", "Road repairs explain why pickup has moved to the college.", "cause and effect"),
         q("What should participants bring?", ["Their own lunch", "A museum guidebook", "A bus timetable", "A college application"], "Да, кафе в музее закрыто", "The employee confirms that lunch is needed because the cafe is closed.")]),
    ("1+", "Workplace", "dialogue", "Listen to colleagues discussing a work arrangement.", [
        "Я завтра работаю дома. Документы для встречи отправить тебе сегодня?",
        "Отправь утром, пожалуйста. Сегодня клиент ещё может изменить заказ.",
        "Хорошо. Но после одиннадцати у меня не будет интернета: придёт мастер.",
        "Тогда пришли файлы до десяти. Я распечатаю их в офисе.",
        "Если клиент позвонит позже, как мне сообщить об изменениях?",
        "Позвони на мой мобильный. Я буду на встрече только с двух часов."],
     "Familiar work coordination with time constraints and a straightforward contingency.", [
         q("Why should the documents wait until morning?", ["The client's order may still change", "The office printer is broken today", "The meeting has already been canceled", "The home internet is unavailable tonight"], "Сегодня клиент ещё может изменить заказ", "Possible order changes are the stated reason for waiting.", "cause and effect"),
         q("How should later changes be communicated?", ["By calling a mobile phone", "By mailing printed documents", "By visiting the client's home", "By leaving a message at reception"], "Позвони на мой мобильный", "The colleague asks for a phone call if changes come later.")]),
    ("2", "Transportation", "interview", "Listen to an interview about a local service.", [
        "В прошлом месяце в районе запустили вечерний автобус. Что показали первые результаты?",
        "Пассажиров оказалось больше, чем мы ожидали, особенно после девяти. Но многие жаловались, что последняя остановка слишком далеко от больницы.",
        "Маршрут уже изменили?",
        "Пока нет. Сначала нужно проверить, сможет ли большой автобус развернуться у главного входа. На этой неделе там проведут пробный проезд без пассажиров.",
        "А расписание останется прежним?",
        "Да. Если испытание пройдёт успешно, добавим остановку со следующего месяца. Время отправления с вокзала и стоимость билета менять не планируем."],
     "Factual account of a service trial, complaint, feasibility check and conditional future action.", [
         q("What concern did passengers raise?", ["The final stop is too far from the hospital", "The first bus leaves before the station opens", "Evening tickets cost more than daytime tickets", "There are too few seats on the morning route"], "последняя остановка слишком далеко от больницы", "Passengers objected to the distance between the last stop and the hospital."),
         q("What must happen before a stop is added?", ["A bus must complete a turning test", "The hospital must sell monthly passes", "The station must extend its opening hours", "Passengers must approve a higher fare"], "сможет ли большой автобус развернуться у главного входа", "A maneuverability check at the entrance is the condition for the change.", "sequence"),
         q("What is expected to remain unchanged?", ["The station departure time and fare", "The final stop and hospital entrance", "The number of passengers after nine", "The date and location of the trial"], "Время отправления с вокзала и стоимость билета менять не планируем", "The speaker explicitly rules out planned changes to departure time and price.")]),
    ("2", "Public services", "interview", "Listen to a discussion of a community service.", [
        "В библиотеке теперь можно брать инструменты. Как устроена эта услуга?",
        "Мы начали с небольшого набора для домашнего ремонта. Читатель выбирает инструмент в каталоге и бронирует его на три дня. Перед первой выдачей сотрудник объясняет правила пользования.",
        "Что оказалось самым сложным?",
        "Раньше возвращённые вещи сразу предлагали следующему человеку. Оказалось, что на проверку состояния нужно время. Поэтому между бронированиями теперь оставляют один свободный день.",
        "Планируете покупать новое оборудование?",
        "Сначала посмотрим, что чаще спрашивают. Деньги выделены, но покупать много редких инструментов, которые будут лежать без дела, мы не хотим."],
     "Everyday organizational process with a past problem, corrective sequence and resource plan.", [
         q("What is required before a reader first borrows a tool?", ["An explanation of the usage rules", "A paid course in home renovation", "A reference from another borrower", "A purchase from the library shop"], "Перед первой выдачей сотрудник объясняет правила пользования", "A staff explanation precedes the first loan."),
         q("Why is a day left between reservations?", ["To check the returned equipment", "To teach the next repair course", "To renew each reader's membership", "To transport tools to another city"], "на проверку состояния нужно время", "Returned tools need an inspection before the next borrower receives them.", "cause and effect"),
         q("What will guide equipment purchases?", ["The tools people request most often", "The oldest entries in the catalog", "The number of books returned late", "The brands used in staff members' homes"], "Сначала посмотрим, что чаще спрашивают", "The library will observe demand before expanding its stock.")]),
    ("2+", "Environment", "discussion", "Listen to two participants discussing a proposal.", [
        "На собрании предложили посадить деревья на месте части парковки. Многие поддержали идею, но владельцы машин считают, что их просто выталкивают из двора.",
        "Их можно понять: вечером свободных мест почти нет. Однако летом площадка так нагревается, что дети даже не выходят играть. Сохранить всё как есть — тоже решение, и у него есть цена.",
        "Значит, надо сначала найти другую парковку?",
        "Это помогло бы, но ждать идеального участка можно годами. Я бы начал с нескольких мест у пустующей стены. Там поставим скамейки и большие ёмкости с растениями. Если станет удобнее, обсудим постоянную посадку.",
        "Не получится ли, что временное благоустройство выдадут за решение всей проблемы?",
        "Такой риск есть. Поэтому нужно заранее назвать, что именно проверяем: станет ли площадка пригоднее для отдыха и насколько изменится ситуация с парковкой. Красивые фотографии сами по себе ответа не дадут."],
     "Competing practical interests, qualification and an evaluative distinction between trial evidence and publicity.", [
         q("What does the second speaker mean by saying that doing nothing has a price?", ["Keeping parking unchanged also has negative consequences", "Residents will have to buy tickets to enter the courtyard", "The proposed plants are more expensive than expected", "The city has already imposed a charge for delayed work"], "Сохранить всё как есть — тоже решение, и у него есть цена", "The phrase frames existing heat and lost recreation as costs of inaction.", "meaning from context"),
         q("Why does the speaker favor a limited temporary trial?", ["It allows a practical test while a complete solution remains difficult", "It removes the need to discuss parking with residents in future", "It guarantees the entire courtyard will receive permanent trees", "It transfers every maintenance task to the owners of parked cars"], "Если станет удобнее, обсудим постоянную посадку", "The reversible first step supplies evidence before committing to permanent planting.", "inference"),
         q("What would count as useful evidence for evaluating the trial?", ["Changes in recreational usability and parking conditions", "The number of attractive photographs posted online", "The price of replacing every car with public transport", "The amount of time residents spend at official meetings"], "пригоднее для отдыха и насколько изменится ситуация с парковкой", "The speaker wants outcomes for both uses, not just visual publicity.")]),
    ("2+", "Education", "discussion", "Listen to a discussion about a training program.", [
        "Курсы для сотрудников получили отличные отзывы, но руководитель сомневается, стоит ли продлевать программу. Разве высокая оценка участников ничего не значит?",
        "Значит, но отвечает на другой вопрос. Людям мог понравиться преподаватель, а применять новые навыки на работе им просто негде. Удовольствие от занятия и его польза не всегда совпадают.",
        "Тогда надо проверить знания сразу после курса?",
        "Это покажет, что запомнили. Я бы ещё поговорил с участниками через месяц и спросил, какую рабочую задачу они теперь решают иначе. Причём не только с самыми активными.",
        "А если изменений не будет, программу закроют?",
        "Не спешил бы. Возможно, проблема в том, что начальники требуют работать по-старому. Тогда менять нужно не содержание курса, а условия, в которых человек пытается использовать выученное. Иначе мы будем ремонтировать ключ, когда заела дверь."],
     "Qualified reasoning about evaluation, an alternative causal explanation and a transparent metaphor.", [
         q("Why are positive reviews insufficient to establish the program's usefulness?", ["Enjoying instruction does not establish workplace application", "Participants are unable to remember their instructor's name", "Managers have already decided to remove the entire course", "Immediate tests cannot measure anything taught in a classroom"], "Удовольствие от занятия и его польза не всегда совпадают", "Satisfaction and practical transfer answer different evaluation questions.", "relationship of ideas"),
         q("What alternative explanation is offered for a lack of workplace change?", ["Managers may prevent employees from using new skills", "Employees may have been moved to a different city", "The course may have been restricted to new managers", "The instructor may have refused to give any examples"], "начальники требуют работать по-старому", "Existing work requirements may block application even if learning occurred.", "inference"),
         q("What does the final metaphor warn against?", ["Revising training when workplace conditions block its use", "Providing employees with practical tools before testing them", "Repeating an evaluation after participants return to work", "Asking less active participants to explain their experiences"], "ремонтировать ключ, когда заела дверь", "Repairing the key instead of the jammed door parallels fixing training instead of its context.", "meaning from context")]),
    ("3", "Government and politics", "interview", "Listen to an interviewer and an analyst discussing public consultation.", [
        "В городе провели опрос о будущем старого завода. Большинство выбрало культурный центр. Почему вы считаете, что это ещё не готовое решение?",
        "Потому что согласие с привлекательной целью не равно согласию с условиями её достижения. Вопрос предлагал сравнить культурный центр с пустующим зданием. О расходах на содержание и возможном сокращении других программ участникам не сообщили. Мы узнали, какой образ будущего им нравится, но не выяснили, от чего они готовы отказаться.",
        "Получается, власти должны были сразу включить в вопрос все финансовые расчёты? Такой опрос никто не дочитает.",
        "Разумеется, перегружать анкету бессмысленно. Но между подробной сметой и обещанием бесплатного праздника есть пространство для честного выбора. Можно предложить несколько осуществимых вариантов с понятными последствиями. И отдельно спросить тех, кто пользуется программами, которые могут потерять финансирование. Иначе большинство невольно распоряжается чужими потерями.",
        "Не даст ли такая осторожность удобный повод бесконечно откладывать проект?",
        "Даст, если обсуждение не имеет срока и никто не отвечает за следующий шаг. Поэтому процедура должна завершаться решением, а не новым кругом обещаний. Я не предлагаю искать вариант, который понравится всем. Я предлагаю сделать разногласия видимыми до того, как торжественное открытие объявят доказательством всеобщей поддержки. Несогласие после осознанного выбора — не обязательно провал участия; иногда это признак того, что участие было настоящим."],
     "Professional argument with concession, unstated opportunity costs, hypothetical alternatives and a qualified view of disagreement.", [
         q("What does the analyst infer about the original poll?", ["It measured attraction to an outcome without testing acceptance of its tradeoffs", "It established a binding agreement among every group affected by the project", "It demonstrated that operating costs would be lower than renovation costs", "It showed that residents preferred an empty building to any cultural activity"], "какой образ будущего им нравится, но не выяснили, от чего они готовы отказаться", "Preferences for a desirable image do not establish consent to the sacrifices required.", "inference"),
         q("Why does the analyst want to hear separately from users of threatened programs?", ["A majority's preferred option may impose costs on a less visible group", "Those users are likely to possess the building's detailed engineering plans", "The city is required to give every existing program an identical budget", "The analyst expects these users to agree with the project without conditions"], "большинство невольно распоряжается чужими потерями", "Separate consultation makes otherwise obscured burdens part of the decision.", "speaker/writer intent"),
         q("Which principle best summarizes the analyst's position?", ["Make tradeoffs explicit and decide within an accountable process", "Delay action until every resident supports the same proposal", "Replace public consultation with detailed financial calculations", "Treat the opening ceremony as proof that disagreement has ended"], "процедура должна завершаться решением", "The analyst combines honest discussion of consequences with a deadline and responsibility for a decision.", "main idea")]),
    ("3", "Science and technology", "interview", "Listen to a discussion about evaluating professional work.", [
        "Университет предлагает оценивать исследовательские группы по числу опубликованных статей. Это ведь понятный и одинаковый для всех показатель. В чём ваше возражение?",
        "В том, что одинаковая линейка не делает измеряемые вещи одинаковыми. В одном проекте результат можно разбить на несколько коротких публикаций, в другом годы уходят на проверку метода, без которой последующие выводы ничего не стоят. Если вознаграждать только скорость появления статей, мы рискуем получить именно скорость, а не более надёжное знание.",
        "Но экспертная оценка тоже небезупречна: на неё влияют репутация автора и личные связи.",
        "Согласен. Отказ от подсчёта сам по себе не создаёт справедливости. Поэтому я предлагаю сочетать показатели с разбором конкретных результатов и публиковать основания оценки. Числа должны помогать задавать вопросы, а не освобождать от необходимости отвечать на них. Особенно важно замечать полезную работу, которая не заканчивается новой статьёй: например, обнаруженную ошибку или проверку чужого результата.",
        "То есть прозрачная процедура важнее точного рейтинга?",
        "Я бы не противопоставлял их так резко. Рейтинг полезен, пока мы понимаем, какие различия он скрывает. Опасность начинается, когда сотрудники перестраивают работу ради места в таблице, а руководство принимает улучшение таблицы за улучшение науки. Тогда показатель перестаёт быть окном и становится декорацией. Возможность объяснить исключение из правила здесь не слабость системы, а защита от её слепых зон."],
     "Extended professional argument about incentives, concession, metaphor and the limitations of a uniform metric.", [
         q("What risk does the speaker associate with rewarding publication speed?", ["Researchers may optimize output counts at the expense of reliability", "Researchers may stop communicating their findings to other teams", "Universities may abandon all attempts to compare different projects", "Expert panels may become completely independent of author reputation"], "получить именно скорость, а не более надёжное знание", "Incentives can produce more countable output without improving the underlying quality.", "inference"),
         q("How does the speaker respond to concerns about biased expert judgment?", ["Accepts the concern and proposes combining scrutiny with explicit criteria", "Rejects the concern because numerical rankings also contain errors", "Concludes that reputation is the best available measure of research", "Suggests that researchers should select their own final rating"], "сочетать показатели с разбором конкретных результатов и публиковать основания оценки", "The response is a transparent combination rather than exclusive reliance on either method.", "relationship of ideas"),
         q("What does the image of a window becoming decoration suggest?", ["A metric can display success while concealing the reality it should reveal", "A university can attract visitors by placing rankings near its entrance", "A research result becomes more accurate when presented in a table", "A publication count is useful only for comparing building designs"], "руководство принимает улучшение таблицы за улучшение науки", "The metaphor contrasts genuine insight with a surface display optimized for appearances.", "meaning from context")]),
]


def build_items():
    result = []
    question_index = 0
    for skill, records in (("reading", READING), ("listening", LISTENING)):
        for index, (level, topic, genre, orientation, source, reason, qs) in enumerate(records, 1):
            item_id = f"ru_expand_{skill[0]}_{level.replace('+', 'p')}_{index:02d}"
            turns = [Turn(speaker="AB"[n % 2], text=t) for n, t in enumerate(source)] if skill == "listening" else []
            text = "\n".join(f"{t.speaker}: {t.text}" for t in turns) if turns else source
            metadata = GenerationMetadata(provider="AI-assisted original authoring", model="Codex",
                prompt_version="russian-range-expansion-v1", authoring_notes="Original fictional scenario. Provisional ILR; no empirical calibration or independent expert review.")
            questions = []
            for n, (stem, answers, evidence, rationale, kind) in enumerate(qs, 1):
                offset = question_index % 4
                choices = answers[-offset:] + answers[:-offset] if offset else answers
                questions.append(QuestionItem(id=f"{item_id}_q{n}", passage_id=item_id, stem_en=stem,
                    choices=dict(zip("ABCD", choices)), correct_key="ABCD"[offset], rationale_en=rationale,
                    evidence_ru=evidence, question_type=kind, target_ilr=level, provisional_difficulty=ILR_THETA[level], generation=metadata))
                question_index += 1
            passage = PassageItem(id=item_id, skill=skill, target_ilr=level, provisional_difficulty=ILR_THETA[level],
                genre=genre, topic=topic, subtopic=f"Original {genre}", orientation_en=orientation, passage_ru=text,
                provenance={"authoring":"Original fictional AI-assisted practice material", "difficulty_rationale":reason,
                            "descriptor_reference":f"https://govtilr.org/Skills/{skill.title()}.htm"},
                word_count=target_unit_count(text, "ru"), question_ids=[x.id for x in questions],
                content_hash=content_hash(text), duplicate_detection_hash=content_hash(text), generation=metadata)
            item = ContentItem(id=item_id, passage=passage, questions=questions, turns=turns,
                speakers={"A":"First speaker (Jessica)", "B":"Second speaker (Eric)"} if turns else {})
            for report in [validate_passage(passage, questions), *[validate_question(x, passage) for x in questions]]:
                if report.status != "accepted":
                    raise ValueError(f"{item_id}: {report.failure_reasons} {report.ambiguity_flags}")
            result.append(item)
    return result


if __name__ == "__main__":
    items = build_items()
    write_package(ROOT / "data/pilots/russian_range_expansion.json", ContentPackage(items=items))
    chars = sum(len(t.text) for i in items for t in i.turns)
    print(f"Built {len(items)} original drafts; {sum(len(i.questions) for i in items)} questions; {chars} listening input characters. No provider called.")
