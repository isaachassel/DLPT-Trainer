"""Final ALES coverage batch: 94 remaining senses in 24 fictional dialogues."""

# Preserve imported IDs/glosses; clarify contextual usage rather than silently
# rewriting the user's source glossary. These notes are shown after the check.
GLOSSARY_NOTES = {
    'ales_e6_museum_1': 'The imported gloss is "missile unit"; here the term names the launcher shown in a photograph.',
    'ales_e6_museum_2': 'The imported gloss is "rocket launcher"; here ракетоносец denotes the missile-carrying aircraft, not a ground launcher.',
    'ales_e6_tremor_2': 'The imported gloss is "to exceed"; превышение is a noun, meaning an excess or exceeding a limit.',
}

SPECS = [
('e6_diplomacy', 2, 'Editing a diplomatic news brief', [
('A', 'Новый выпуск посвящён Ближнему Востоку. В первом сообщении обсуждают мирный договор, но полный текст ещё не получен.'),
('B', 'Кто подтвердил эту информацию?'),
('A', 'Правительственный источник. Договор собираются вводить в силу осенью. Редактор просит проверить дату перед публикацией.')], '''
Ближний Восток|Middle East|Ближнему Востоку|the Middle East|the Far East;Central Asia;Eastern Europe|Which region is the new edition about?|Доклад посвящён Ближнему Востоку.
мирный договор|peace treaty|мирный договор|peace treaty|trade agreement;defense pact;border permit|What document is discussed in the first report?|Стороны обсуждают мирный договор.
правительственный|governmental|Правительственный|government|opposition;academic;commercial|What kind of source confirmed the information?|Правительственный доклад появится завтра.
вводить в силу|to bring into effect, to enforce|вводить в силу|bring into effect|submit for debate;translate;cancel|What do they intend to do with the treaty in autumn?|Новые правила будут вводить в силу постепенно.
'''),
('e6_bulletin', 3, 'Checking a historical bulletin', [
('A', 'В сводке говорится, что бой закончился ночью. Войска оставались за рекой, но точное место на карте не отмечено.'),
('B', 'Откуда автор получил сведения?'),
('A', 'Он ссылается на разведку. В приложении есть боевой приказ, однако его дату ещё проверяют по архивным документам.')], '''
бой|battle, combat, fight|бой|battle|march;meeting;exercise|What ended during the night?|Этот бой описан в воспоминаниях.
войска (pl.)|forces|Войска|troops|refugees;reporters;negotiators|Who remained beyond the river?|Войска вернулись после учений.
разведка|intelligence, reconnaissance|разведку|intelligence service|local press;medical service;city council|What source of information does the author cite?|В докладе упоминают разведку.
боевой|combat (attr.), fighting|боевой|combat|administrative;ceremonial;medical|What type of order appears in the appendix?|В музее хранится боевой журнал.
'''),
('e6_museum', 3, 'Reviewing military museum labels', [
('A', 'На первой фотографии ракетная установка. Рядом показан ракетоносец в полёте, но подпись к нему пока не готова.'),
('B', 'А что изображено на схеме под фотографиями?'),
('A', 'Боеголовка. Для следующего стенда выбрали зенитный комплекс. Экскурсовод просит проверить все названия до открытия выставки.')], '''
ракетная установка|missile unit|ракетная установка|missile launcher|radar station;fuel tanker;field hospital|What is shown in the first photograph?|На снимке видна ракетная установка.
ракетоносец|rocket launcher|ракетоносец|missile-carrying aircraft|transport aircraft;refueling aircraft;reconnaissance aircraft|What type of aircraft is shown in flight nearby?|На выставке показан старый ракетоносец.
боеголовка|warhead|Боеголовка|warhead|engine;guidance antenna;fuel tank|What component is depicted in the diagram?|Боеголовка обозначена на музейной схеме.
зенитный|antiaircraft|зенитный|antiaircraft|antitank;coastal-defense;communications|What role does the system chosen for the next display have?|В книге описан зенитный комплекс.
'''),
('e6_energy', 2, 'Planning an energy documentary', [
('A', 'В первой части фильма показана атомная электростанция. Вторая часть рассказывает про нефтяной терминал у моря.'),
('B', 'Какие слова нужно объяснить в словаре к фильму?'),
('A', 'Редактор выделил слово «ядерный». Ещё будет схема, на которой изображена сеть городских станций. Подписи к ней готовят отдельно.')], '''
атомная электростанция|nuclear power station|атомная электростанция|nuclear power station|hydroelectric dam;coal-fired station;wind farm|What facility appears in the first part?|За городом расположена атомная электростанция.
нефтяной|oil (attr.)|нефтяной|oil|grain;passenger;container|What type of terminal is the second part about?|В порту строят нефтяной терминал.
ядерный|nuclear|ядерный|nuclear|thermal;hydraulic;electrical|What does the word singled out for the glossary mean?|В статье встречается термин «ядерный».
сеть|network|сеть|network|output;budget;construction timetable|What aspect of the city’s stations does the diagram show?|В регионе появилась новая сеть магазинов.
'''),
('e6_explosion', 3, 'Clarifying a fictional incident report', [
('A', 'В сообщении упомянут взрыв у пустого склада. Причину пока не назвали, и редактор не хочет делать выводы.'),
('B', 'В тексте есть слова «взрывное устройство»?'),
('A', 'Да. Эксперт проверяет, мог ли обнаруженный заряд взорваться. До его заключения заметку решили не публиковать.')], '''
взрыв|explosion|взрыв|explosion|fire;collapse;power failure|What event is mentioned near the empty warehouse?|В пьесе за сценой слышен взрыв.
взрывное устройство|blasting device|взрывное устройство|explosive device|tracking device;fire extinguisher;warning siren|What kind of object does the second speaker ask whether the report mentions?|В романе полиция обнаружила взрывное устройство.
заряд|charge|заряд|explosive charge|electrical bill;criminal accusation;radio message|What object’s possible behavior is being examined?|На музейной схеме отмечен заряд.
взрываться/взорваться|to explode|взорваться|explode|sink;leak;overheat|What does the expert want to determine whether the object could do?|В фильме старый снаряд мог взорваться.
'''),
('e6_safety', 2, 'Reviewing a safety announcement', [
('A', 'В объявлении сказано, что специалисты смогли обезвредить опасный предмет. Остальные детали пока уточняются.'),
('B', 'Что решили сделать с испорченными материалами?'),
('A', 'Их решили уничтожить. Кроме того, предложили усилить охрану склада и прекратить ночные работы. Решение обсудят утром.')], '''
обезвредить (вред 51)|to render harmless|обезвредить|render harmless|identify;locate;transport|What did specialists manage to do to the dangerous object?|Специалисты должны обезвредить находку.
уничтожать/уничтожить|to destroy|уничтожить|destroy|inspect;return;store|What was decided for the damaged materials?|Старые копии решили уничтожить.
усиливать/усилить|to increase, to intensify|усилить|strengthen|reduce;replace;inspect|What change to warehouse security was proposed?|Организаторы решили усилить контроль.
прекращать/прекратить|to stop, to terminate|прекратить|stop|extend;reschedule;supervise|What did they propose doing with night work?|Шум попросили прекратить до начала встречи.
'''),
('e6_attack', 3, 'Discussing a fictional news script', [
('A', 'В сценарии вооружённый человек появляется у моста. Редактор просит уточнить, кто он и откуда пришёл.'),
('B', 'В следующей сцене его называют боевиком?'),
('A', 'Да. Дальше описано нападение на пост. Кто решил напасть первым, автор пока не объяснил. Этот эпизод ещё будут обсуждать.')], '''
вооружённый|armed|вооружённый|armed|wounded;uniformed;masked|How is the person at the bridge described?|В рассказе появляется вооружённый охранник.
боевик|fighter|боевиком|militant fighter|civilian witness;police officer;aid worker|What is the character called in the next scene?|В романе этот человек оказался боевиком.
нападение|attack|нападение|attack|inspection;withdrawal;negotiation|What event at the post is described?|Нападение стало темой вечернего выпуска.
нападать/напасть|to attack|напасть|attack|retreat;surrender;negotiate|What action does the author leave unexplained as to who decided to take it first?|Герой опасался, что на него могут напасть.
'''),
('e6_testimony', 3, 'Reviewing a courtroom scene', [
('A', 'Обвинитель попросил вызвать директора. Его хотят обвинить в передаче документов, но дело ещё рассматривают.'),
('B', 'Он согласился свидетельствовать?'),
('A', 'В тексте ответа нет. Следователь продолжает подозревать другого сотрудника. Автор обещал уточнить роли персонажей в следующей версии.')], '''
обвинитель|prosecutor, accuser|Обвинитель|prosecutor|defense lawyer;judge;court clerk|Who asked for the director to be called?|Обвинитель выступит после перерыва.
обвинять/обвинить (вина 43)|to accuse|обвинить|accuse|acquit;reward;question informally|What do they intend to do concerning the transfer of documents?|Его пытались обвинить в нарушении правил.
свидетельствовать|to testify, to bear witness to|свидетельствовать|testify|appeal;confess;serve on a jury|What does the second speaker ask whether the person agreed to do?|Она согласилась свидетельствовать в суде.
подозревать|to suspect|подозревать|suspect|defend;convict;release|What attitude does the investigator still have toward another employee?|Без доказательств нельзя подозревать каждого.
'''),
('e6_customs', 3, 'Editing a customs report', [
('A', 'В черновике упомянута контрабанда. На складе нашли партию наркотиков, но её происхождение ещё проверяют.'),
('B', 'Кого решили задержать?'),
('A', 'Водителя. В машине также был несовершеннолетний пассажир. Редактор просит не включать его имя в заметку и дождаться уточнений.')], '''
контрабанда|smuggling, contraband|контрабанда|smuggling|tax evasion;forgery;fraud|What activity is mentioned in the draft?|Контрабанда обсуждалась в документальном фильме.
партия (наркотиков)|batch (of drugs)|партию наркотиков|batch of drugs|list of medicines;medical prescription;package of test equipment|What was found at the warehouse?|В сводке упомянули партию наркотиков.
задерживать/задержать|to detain|задержать|detain|fine;escort;question by phone|What did they decide to do with the driver?|В рассказе приказали задержать курьера.
несовершеннолетний|under legal age, minor|несовершеннолетний|under legal age|foreign;unaccompanied;injured|How is the passenger described?|На встречу пришёл несовершеннолетний участник.
'''),
('e6_inquiry', 3, 'Checking a crime-documentary outline', [
('A', 'В начале фильма упоминается Федеральное бюро расследования. Затем автор рассказывает, когда начался розыск.'),
('B', 'Кого ищут в этой истории?'),
('A', 'В письме сказано: преступника. Позднее его называют убийцей, но редактор просит уточнить, на каком документе основано это утверждение.')], '''
Федеральное бюро расследования (ФБР)|Federal Bureau of Investigation (FBI)|Федеральное бюро расследования|Federal Bureau of Investigation|Central Intelligence Agency;Department of Justice;Secret Service|Which agency is mentioned at the beginning?|В статье упоминается Федеральное бюро расследования.
розыск|search|розыск|search for a wanted person|trial;interrogation;extradition|What process’s beginning does the author describe?|Розыск продолжался несколько месяцев.
преступник|criminal|преступника|criminal|witness;informant;investigator|How does the letter identify the person sought?|В романе искали преступника.
убийца|murderer|убийцей|murderer|robber;smuggler;forger|What is that person called later?|Герой рассказа оказался убийцей.
'''),
('e6_recruitment', 3, 'Preparing an archive interview', [
('A', 'В архиве есть папка под названием «Вербовка». В ней описано, как организатор пытался завербовать новых участников.'),
('B', 'Для какой группы он работал?'),
('A', 'В письме упомянут подпольный кружок. Один сосед сумел подслушать разговор, но его воспоминания записали только спустя много лет.')], '''
вербовка|recruitment|Вербовка|recruitment|surveillance;fundraising;training|What subject is named on the folder?|Вербовка стала темой исследования.
вербовать/завербовать|to recruit|завербовать|recruit|dismiss;interrogate;transport|What did the organizer try to do with new participants?|Организатор хотел завербовать сторонников.
подпольный|underground|подпольный|clandestine|official;international;temporary|How is the circle described?|В книге описан подпольный журнал.
подслушивать/подслушать|to eavesdrop, to overhear|подслушать|overhear|record with permission;interrupt;translate|What did the neighbor manage to do with the conversation?|Он не хотел подслушать чужой разговор.
'''),
('e6_report', 3, 'Checking wording in a fictional report', [
('A', 'Репортаж пока не готов. В нём говорится, что охранника пытались застрелить, но исход этого эпизода ещё уточняют.'),
('B', 'А кто упомянут в следующем абзаце?'),
('A', 'Убитый свидетель. Остальной текст редактор обещал прислать вечером. До этого не будем соединять два эпизода в одну историю.')], '''
репортаж|reporting|Репортаж|news report|advertisement;editorial;official decree|What is not ready yet?|Репортаж выйдет в воскресенье.
застрелить (стрелять 16)|to shoot, to kill|застрелить|shoot dead|abduct;arrest;intimidate|What does the report say someone attempted to do to the guard?|В сценарии злодей хотел застрелить героя.
убитый|killed|Убитый|killed|missing;injured;detained|What is the stated condition of the witness in the next paragraph?|Убитый персонаж появляется только в воспоминаниях.
остальной|remaining, the rest|Остальной|remaining|original;translated;rejected|Which portion of the text will the editor send later?|Остальной материал находится в архиве.
'''),
('e6_memorial', 2, 'Preparing a memorial exhibit', [
('A', 'Первый стенд рассказывает про гибель экспедиции. В дневнике есть запись о том, что один участник мог погибнуть ещё до прибытия помощи.'),
('B', 'Что изображено на рисунке рядом?'),
('A', 'Мёртвый олень у дороги. В последнем разделе обсуждается смерть руководителя. Даты ещё проверяют по письмам.')], '''
гибель|death|гибель|loss of life|return;departure;discovery|What aspect of the expedition is the first display about?|В книге описана гибель путешественников.
погибать/погибнуть|to die, to perish|погибнуть|perish|get lost;fall ill;leave|What might have happened to one member before help arrived?|Герой мог погибнуть во время бури.
мёртвый|dead|Мёртвый|dead|wounded;frightened;trapped|How is the deer in the drawing described?|На берегу лежал мёртвый краб.
смерть|death|смерть|death|appointment;illness;retirement|What event concerning the leader does the final section discuss?|Его смерть упомянута в последней главе.
'''),
('e6_rescue', 2, 'Reviewing a fictional rescue bulletin', [
('A', 'В сообщении названа только одна жертва аварии. Раненый пассажир пока не смог ответить на вопросы журналиста.'),
('B', 'А что известно о водителе?'),
('A', 'Он мог получить ранение ещё утром, но сумел остаться в живых. Других сведений редакция пока не получила, поэтому заметка будет короткой.')], '''
жертва|victim, casualty|жертва|victim|witness;rescuer;suspect|What role does the one person named in the report have?|Жертва происшествия дала интервью.
раненый|wounded, injured|Раненый|injured|exhausted;frightened;unconscious|How is the passenger described?|Раненый герой оставался в палатке.
получать/получить ранение|to be wounded, to be injured|получить ранение|be injured|receive treatment;lose consciousness;be evacuated|What may have happened to the driver earlier that morning?|Персонаж мог получить ранение в дороге.
оставаться/остаться в живых|to survive|остаться в живых|survive|remain at the scene;stay awake;recover fully|What did the driver manage to do despite what happened?|Путешественник сумел остаться в живых.
'''),
('e6_memoir', 2, 'Editing a doctor’s fictional memoir', [
('A', 'В первой главе врач боялся, что пациент может скончаться до приезда родственников. Автор описывает этот случай без имён и точных дат.'),
('B', 'Кто появляется в следующей главе?'),
('A', 'Человек, у которого на руке был шрам. В его рассказе упомянуто снотворное, но название препарата автор решил не включать.')], '''
скончаться|to die|скончаться|die|recover;leave the hospital;fall asleep|What did the doctor fear might happen before the relatives arrived?|По сюжету писатель должен скончаться в последней главе.
случай|occasion|случай|case or occurrence|diagnosis;prescription;appointment|What does the author describe without names or exact dates?|Этот случай запомнился всем участникам.
шрам|scar|шрам|scar|bruise;bandage;tattoo|What did the person in the next chapter have on an arm?|На ладони остался небольшой шрам.
снотворное|medicine taken to induce sleep|снотворное|sleeping medicine|painkiller;antibiotic;antiseptic|What type of medicine is mentioned in the person’s story?|В рассказе упоминается снотворное.
'''),
('e6_collision', 2, 'Comparing two incident accounts', [
('A', 'В первом рассказе машина могла врезаться в ограждение. Автор ещё не решил, чем закончится эта сцена.'),
('B', 'А падение моста относится к тому же эпизоду?'),
('A', 'Нет. Во втором рассказе описаны столкновения на дороге. Там автобус рисковал разбиться, но последние страницы пока отсутствуют.')], '''
врезаться/врезаться|to crash into|врезаться|crash into|stop beside;drive around;pull away from|What might the car do in relation to the barrier?|Машина могла врезаться в дерево.
падение|fall|падение|collapse|construction;inspection;closure|What event involving a bridge does the second speaker ask about?|Падение дерева перекрыло дорогу.
столкновения (столкнуться 43E)|collision, clash, conflict|столкновения|collisions|traffic jams;roadworks;detours|What road events are described in the second story?|Столкновения произошли на разных участках.
разбиваться/разбиться|to crash, to be smashed|разбиться|crash|get delayed;run out of fuel;lose its way|What risk did the bus face?|Лодка могла разбиться о камни.
'''),
('e6_route', 1, 'Following directions to a rehearsal', [
('A', 'После обеда группа должна двинуться к театру. Потом нужно пройти через двор, потому что главный вход закрыт.'),
('B', 'Мы сможем попасть в зал до начала репетиции?'),
('A', 'Думаю, да. Администратор обещал встретить нас у двери. Я ещё уточню время и пришлю сообщение всем участникам.')], '''
двигаться/двинуться|to move|двинуться|set off|send a message;look over;make a call|What should the group do toward the theater after lunch?|Колонна должна двинуться утром.
проходить/пройти (ходить 11)|to go, to pass|пройти|walk through|wait in;inspect;go around|What should the group do in the courtyard?|До площади можно пройти через парк.
попадать/попасть|to get|попасть|get into|find out about;rent;telephone|What do the visitors hope to do concerning the hall before rehearsal?|Без пропуска трудно попасть в здание.
'''),
('e6_fair', 1, 'Planning a community showcase', [
('A', 'На сцену первой выйдет манекенщица. За ней выступит участник, награждённый на прошлогоднем конкурсе.'),
('B', 'У входа уже собралась толпа?'),
('A', 'Да. Наш маленький праздник начинает становиться популярным. Организаторы ещё проверяют список выступающих и готовят места для гостей.')], '''
манекенщица|model|манекенщица|fashion model|singer;presenter;designer|Who will be first on stage?|На встречу пришла известная манекенщица.
награждённый|one who was awarded|награждённый|given an award|disqualified;selected as a judge;invited as an observer|What happened to the next participant at last year’s contest?|Студент, награждённый за работу, выступил первым.
толпа|crowd|толпа|crowd|queue of vehicles;security team;press delegation|What group does the second speaker ask about at the entrance?|Возле вокзала собралась толпа.
становиться/стать|to become|становиться|become|remain;seem;stop being|What change in popularity does the speaker describe?|К вечеру начало становиться холодно.
'''),
('e6_border', 3, 'Reviewing a historical evacuation account', [
('A', 'В тексте упомянут рубеж у реки. Туда направили силы быстрого реагирования, но время прибытия пока не указано.'),
('B', 'Какую задачу описывает автор?'),
('A', 'Освободить жителей, которых удерживали в здании. Позже в рассказе начали обстреливать мост. Этот эпизод редактор просит проверить отдельно.')], '''
рубеж|border, boundary|рубеж|boundary|headquarters;crossing point;settlement|What feature near the river is mentioned?|На карте отмечен прежний рубеж.
силы быстрого реагирования|rapid deployment force|силы быстрого реагирования|rapid-response forces|border inspectors;engineering crews;peace negotiators|Who was sent there?|В сообщении упомянуты силы быстрого реагирования.
освобождать/освободить (свободный 26)|to free, to liberate|Освободить|free|question;register;relocate voluntarily|What was the task concerning the residents held in the building?|Герои решили освободить пленника.
обстреливать/обстрелять|to fire upon, to shell|обстреливать|fire upon|inspect;guard;rebuild|What began happening to the bridge later?|В романе начали обстреливать крепость.
'''),
('e6_resistance', 3, 'Discussing a fictional historical chapter', [
('A', 'Глава называется «Борьба за город». В начале описано сопротивление жителей, но имена участников ещё не названы.'),
('B', 'Как реагирует командир в следующем эпизоде?'),
('A', 'Он приказал применять силу. Однако жители продолжали оказывать сопротивление. Автор хочет сравнить два рассказа об этом событии.')], '''
борьба|struggle, fight|Борьба|struggle|negotiations;celebration;search|What activity is named in the chapter title?|Борьба за первое место продолжалась весь день.
сопротивление|resistance|сопротивление|resistance|cooperation;panic;indifference|What response by residents is described at the beginning?|Предложение встретило сопротивление.
сила|force|силу|force|persuasion;deception;patience|What did the commander order to be used?|В этой сцене решили применить силу.
оказывать сопротивление|to offer resistance|оказывать сопротивление|offer resistance|request assistance;negotiate terms;obey instructions|What did the residents continue to do?|Персонаж продолжал оказывать сопротивление.
'''),
('e6_health', 3, 'Editing a health-conference program', [
('A', 'В программе есть доклад про СПИД. Рядом указан другой доклад, в котором исследуют распространение вируса среди животных.'),
('B', 'Что именно хотят выяснить исследователи?'),
('A', 'Может ли этот вирус заразить новый вид животных. Пока они опасаются делать выводы. Редактор просит не смешивать темы двух докладов.')], '''
СПИД|AIDS|СПИД|AIDS|influenza;hepatitis;malaria|What disease is the first named talk about?|В заголовке статьи упоминается СПИД.
распространение|spreading, expansion|распространение|spread|origin;structure;detection|Which aspect of the animal virus is being studied?|Распространение новостей обсуждали на семинаре.
заражать/заразить|to infect, to contaminate|заразить|infect|protect;attract;frighten|What do researchers want to know whether the virus can do to another species?|В рассказе врач боялся заразить коллегу.
опасаться|to fear|опасаются|are wary of|are eager to;are required to;have agreed to|How do researchers currently feel about drawing conclusions?|Участники опасаются задержки рейса.
'''),
('e6_maritime', 2, 'Preparing a maritime film discussion', [
('A', 'На первой схеме изображён трал. Во второй части фильма судно должно состыковаться с плавучей платформой.'),
('B', 'Какие вопросы задали зрители после просмотра?'),
('A', 'Они спросили, зачем пришлось слить воду из бака. Ещё предложили предусмотреть больше времени для обсуждения. Ответы автора запишут завтра.')], '''
трал|trawl|трал|trawl net|anchor;propeller;mooring line|What piece of equipment is in the first diagram?|В музее показан старый трал.
стыковаться/состыковаться|to dock|состыковаться|dock|communicate by radio;change places;break contact|What should the vessel do with the floating platform?|Корабль должен состыковаться со станцией.
сливать/слить|to pour out|слить|drain|heat;filter;measure|What action involving the water in the tank did viewers ask about?|После опыта нужно слить воду.
предусматривать/предусмотреть|to anticipate, to foresee|предусмотреть|allow for|cut back;record retrospectively;charge extra for|What did viewers propose concerning more discussion time?|В плане нужно предусмотреть перерыв.
'''),
('e6_crime', 3, 'Comparing scenes in a detective story', [
('A', 'В первой сцене преступники собирались совершить налёт на магазин. Дальше они пытались угнать автобус, но автор ещё меняет сюжет.'),
('B', 'Что происходит в разговоре с охранником?'),
('A', 'Один персонаж начинает угрожать ему и требовать ключи. Редактор просит сократить эту сцену и уточнить её место в рассказе.')], '''
совершать/совершить налёт|to raid|совершить налёт|carry out a raid|conduct an inspection;organize a boycott;make a delivery|What were the criminals planning to do at the store?|В романе банда решила совершить налёт на склад.
угонять/угнать|to hijack|угнать|hijack|stop for inspection;charter;repair|What did they later try to do with the bus?|По сюжету преступник пытался угнать самолёт.
угрожать (угроза 40)|to threaten|угрожать|threaten|reassure;deceive;thank|How does one character begin treating the guard?|Герой не позволил угрожать своему другу.
требовать/потребовать|to demand|требовать|demand|offer;hide;return|What does that character do concerning the keys?|Участники стали требовать объяснений.
'''),
('e6_tremor', 2, 'Discussing a monitoring-station log', [
('A', 'Дежурный записал слабый толчок ночью. В журнале также отмечено превышение установленной нормы, но измерение ещё проверяют.'),
('B', 'Прибор уже удалось настроить?'),
('A', 'Первая попытка была неудачной. Завтра приедет специалист и посмотрит все записи. До его приезда отчёт останется предварительным.')], '''
толчок|tremor|толчок|tremor|noise;flash;gust|What did the observer record during the night?|Жители почувствовали слабый толчок.
превышение|to exceed|превышение|exceeding the limit|reaching the minimum;meeting the average;falling below the limit|What relationship to the established norm is noted in the log?|В отчёте отмечено превышение расходов.
попытка|attempt|попытка|attempt|measurement;delivery;forecast|What was unsuccessful the first time?|Вторая попытка оказалась удачной.
'''),
]
