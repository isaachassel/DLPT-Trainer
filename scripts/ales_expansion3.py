"""Third ALES batch: original fictional dialogues for 80 new glossary senses."""

SPECS = [
('e3_family', 1, 'Identifying a visitor', [
('A', 'Завтра приедет мой близнец. Я оставлю для него ключ у администратора.'),
('B', 'Что мне сказать, если администратор попросит его описать?'),
('A', 'У него русые волосы. Возраст указан в заявке, а рост я забыл записать. Если возникнут вопросы, пусть позвонят мне. Фотографию я пришлю отдельно.')], '''
близнец|twin|близнец|a twin|a cousin;a nephew;a brother-in-law|Who is arriving tomorrow?|Мой близнец живёт в другом городе.
русые волосы|light brown hair|русые волосы|light brown hair|black hair;red hair;blond hair|Which hair description should be given?|У моей сестры русые волосы.
возраст|age|Возраст|age|occupation;citizenship;address|Which detail is already on the application?|Возраст участников не ограничен.
рост|height|рост|height|weight;shoe size;eye color|Which detail did the speaker forget to record?|В анкете нужно указать рост.
'''),
('e3_archive', 1, 'Choosing a person to interview', [
('A', 'Для нашего архива согласился дать интервью бывший директор школы. Он недавно закончил свои воспоминания.'),
('B', 'Это тот пожилой мужчина, который был на встрече в пятницу?'),
('A', 'Да, седой мужчина у окна. Я договорилась принести ему список вопросов. Сначала он хочет прочитать их дома.')], '''
бывший|former|бывший|former|current;temporary;deputy|How is the interviewee’s connection with the school described?|Бывший тренер пришёл посмотреть матч.
воспоминания|memoirs, reminiscences|воспоминания|memoirs|a textbook;a budget;a dictionary|What has the interviewee recently finished?|Её воспоминания опубликовали в журнале.
пожилой|getting on in years|пожилой|elderly|middle-aged;young;underage|What age description does the second speaker use?|Пожилой сосед попросил помочь с сумками.
седой|grey|седой|gray-haired|bald;dark-haired;red-haired|Which appearance detail identifies the man by the window?|Седой посетитель оставил зонт у двери.
'''),
('e3_award', 2, 'Preparing an awards event', [
('A', 'Вручение дипломов начнётся после обеда. Организаторы хотят, чтобы вечер был торжественным, но не слишком длинным.'),
('B', 'Кто будет поздравлять участников?'),
('A', 'Ректор. Он сказал, что для него большая честь выступить перед ними. После этого гости смогут поговорить друг с другом.')], '''
вручение|delivery, presentation|Вручение|presentation|printing;checking;replacement|What will happen to the diplomas after lunch?|Вручение наград перенесли на вечер.
торжественный|solemn|торжественным|ceremonial|informal;humorous;competitive|What tone do the organizers want for the evening?|Открытие музея было торжественным.
поздравлять/поздравить|to congratulate|поздравлять|congratulate|question;instruct;introduce|What action involving the participants does the second speaker ask about?|Мы будем поздравлять коллегу завтра.
честь|honor|честь|an honor|a duty;a burden;a surprise|What does the rector call the opportunity to speak?|Для меня честь работать с этой командой.
'''),
('e3_lab', 2, 'Planning a university exhibit', [
('A', 'Тема выставки — наука в повседневной жизни. Наш научный отдел готовит для неё небольшой стенд.'),
('B', 'Что вы покажете посетителям?'),
('A', 'Новое изобретение наших студентов. Сначала мы хотим испытать его в другой комнате. Если всё будет в порядке, перенесём стенд в главный зал.')], '''
наука|science|наука|science|art;commerce;politics|What is the exhibit’s theme in relation to everyday life?|Его особенно интересует наука.
научный|scientific|научный|scientific|administrative;financial;legal|What kind of department is preparing the display?|Научный журнал вышел в декабре.
изобретение|invention|изобретение|an invention|a historical document;a survey result;a photograph|What student work will visitors see?|Это изобретение изменило работу мастерской.
испытывать/испытать|to test|испытать|test|repair;sell;dismantle|What will the speakers do before moving the display?|Прибор нужно испытать на улице.
'''),
('e3_press', 2, 'Preparing a publication', [
('A', 'Наш еженедельник готовит специальное издание. Материалы уже собраны, но оформление ещё не закончено.'),
('B', 'Когда вы собираетесь выпустить его?'),
('A', 'В пятницу. Один иностранный автор попросил прислать ему экземпляр. Я записал адрес и передам его человеку, который занимается отправкой.')], '''
еженедельник|weekly|еженедельник|a weekly publication|a daily publication;a monthly publication;an annual publication|What kind of periodical is preparing the project?|Этот еженедельник продаётся у станции.
издание|publication, edition|издание|edition|subscription;interview;exhibition|What special product is being prepared?|Новое издание книги уже поступило в библиотеку.
выпускать/выпустить|to release, to publish|выпустить|publish|translate;withdraw;review|Which action is planned for Friday?|Редактор хочет выпустить сборник летом.
иностранный|foreign|иностранный|foreign|local;anonymous;retired|How is the author requesting a copy described?|Иностранный журналист задал вопрос.
'''),
('e3_travel', 2, 'Preparing for a work visit', [
('A', 'В этом месяце мне предстоит совершить поездку по работе. Встреча пройдёт за рубежом.'),
('B', 'Граница далеко от места встречи?'),
('A', 'Я ещё не посмотрел карту. Это международный проект, поэтому документы готовят сразу несколько организаций. Билеты обещали прислать завтра.')], '''
совершать/совершить поездку|to make a trip|совершить поездку|make a trip|cancel a trip;finance a trip;describe a trip|What does the first speaker expect to do for work?|Мы планируем совершить поездку в соседний район.
за рубежом|abroad|за рубежом|abroad|nearby;online;at headquarters|Where will the meeting take place?|Её брат учится за рубежом.
граница|border|Граница|the border|the airport;the coast;the capital|What location does the second speaker ask about?|Граница проходит через горы.
международный (между 28, народ 36)|international|международный|international|regional;private;experimental|How is the project described?|Международный фестиваль откроется завтра.
'''),
('e3_contest', 1, 'Discussing an application', [
('A', 'В городе объявили конкурс для молодых архитекторов. Я собираюсь принять участие, но сначала закончу чертежи.'),
('B', 'Ты единственный человек из вашей мастерской, который подал заявку?'),
('A', 'Нет, есть ещё один претендент. Мы работаем отдельно и пока не показываем друг другу свои проекты.')], '''
конкурс|contest, competition|конкурс|a competition|a training course;a conference;a job fair|What has the city announced?|Конкурс продлится до конца недели.
принимать/принять участие|to take part|принять участие|participate|withdraw;judge;organize|What does the first speaker intend to do?|Наш класс хочет принять участие в концерте.
единственный|only, sole|единственный|the only one|the youngest one;the first one;the most experienced one|What does the second speaker ask about the applicant’s position within the workshop?|Это единственный магазин в деревне.
претендент|contender, claimant|претендент|a contender|a judge;a sponsor;a spectator|What role does the other person have?|Новый претендент представил свои документы.
'''),
('e3_pool', 1, 'Discussing an activity at the pool', [
('A', 'Сегодня в программе плавание. Нам сказали подождать у входа примерно десять минут.'),
('B', 'Кто покажет упражнение?'),
('A', 'Пловчиха из местного клуба. Она сначала объяснит задание, а потом попросит нас встать в круг. Я оставлю сумку в шкафчике и сразу вернусь.')], '''
плавание|swimming|плавание|swimming|rowing;diving;water polo|What activity is on today’s program?|Зимой он не бросает плавание.
примерно|approximately|примерно|approximately|exactly;at least;at most|How precise is the stated waiting time?|До станции примерно два километра.
пловец, пловчиха|swimmer (m., f.)|Пловчиха|a swimmer|a gymnast;a runner;a dancer|Who will demonstrate the exercise?|Пловчиха приехала на соревнования.
круг|circle|круг|a circle|a line;pairs;two teams|What formation will the participants be asked to make?|Дети нарисовали круг на земле.
'''),
('e3_outdoors', 1, 'Planning an outing', [
('A', 'На выходные у нас запланирована рыбалка. Мы выбрали залив, о котором рассказал сосед.'),
('B', 'Что мне взять с собой?'),
('A', 'Обязательно сапоги. Окрестности я знаю плохо, поэтому сначала посмотрим карту. Если дорога окажется слишком длинной, выберем другое место и предупредим остальных.')], '''
рыбалка|fishing|рыбалка|fishing|camping;hunting;sailing|What activity is planned for the weekend?|Сегодня рыбалка закончилась раньше обычного.
залив|bay, gulf|залив|a bay|a lake;a river;a canal|What geographical feature have the speakers chosen?|Этот залив хорошо виден с холма.
сапоги|high boots|сапоги|boots|gloves;a raincoat;a hat|What item is specifically recommended?|Я оставил сапоги у двери.
окрестности|environs, suburbs|Окрестности|the surrounding area|the local residents;the weather pattern;the transport schedule|What does the first speaker not know well?|Окрестности города постепенно изменились.
'''),
('e3_office', 1, 'Handling a message at work', [
('A', 'Руководитель попросил передать этот пакет в соседний отдел. Там его ждёт новый сотрудник.'),
('B', 'Он будет на месте после обеда?'),
('A', 'Не знаю, утром он отсутствовал. На пакете написано «срочный», поэтому лучше сначала позвонить. Номер телефона есть в списке у секретаря.')], '''
руководитель|leader|Руководитель|the manager|the customer;the receptionist;the courier|Who requested that the packet be delivered?|Руководитель назначил встречу на вторник.
сотрудник|co-worker, employee|сотрудник|an employee|a visitor;an inspector;a supplier|Who is expecting the packet?|Новый сотрудник быстро освоился.
отсутствовать|to be absent, to lack|отсутствовал|was absent|was busy;was late;was on duty|What is said about the recipient that morning?|Во вторник преподаватель отсутствовал.
срочный|urgent|срочный|urgent|confidential;personal;fragile|How is the packet labeled?|Это срочный вопрос, его нельзя отложить.
'''),
('e3_contract', 2, 'Reviewing paperwork with a partner', [
('A', 'Партнёр прислал договор. В нём появилось новое условие, которого не было в нашем черновике.'),
('B', 'Ты готов подписать документ сегодня?'),
('A', 'Пока нет. Мы хотели заключить его до пятницы, но мне нужно сначала задать несколько вопросов. Я попрошу юриста посмотреть последнюю страницу.')], '''
договор|agreement, treaty|договор|an agreement|an invoice;a complaint;a timetable|What kind of document did the partner send?|Договор лежит в папке у директора.
условие|condition, term|условие|a condition|a signature;a seal;an illustration|What new element appears in the latest version?|Это условие нужно обсудить заранее.
подписывать/подписать|to sign|подписать|sign|translate;deliver;copy|What does the second speaker ask whether the first speaker is ready to do today?|Нужно подписать заявление внизу страницы.
заключать/заключить|to conclude|заключить|conclude|cancel;extend;publish|What had the parties hoped to do by Friday?|Они решили заключить соглашение на год.
'''),
('e3_workspace', 2, 'Preparing a shared workspace', [
('A', 'Мы хотим оборудовать комнату для занятий. Нужен современный проектор, но модель пока не выбрали.'),
('B', 'Кто объяснит правила?'),
('A', 'Инструктор расскажет про использование техники. А наличие свободных мест будем проверять через сайт. Сначала попробуем такую систему в одной комнате.')], '''
оборудовать|to equip|оборудовать|equip|rent;clean;inspect|What do the speakers want to do with the room?|Мы решили оборудовать мастерскую в гараже.
современный|modern|современный|modern|portable;inexpensive;used|What characteristic is requested for the projector?|Этот современный прибор работает тихо.
использование|use|использование|use|purchase;delivery;repair|What topic will the instructor explain regarding the equipment?|Использование телефона здесь запрещено.
наличие|presence, existence|наличие|availability|price;location;size|What aspect of the free places will be checked online?|Наличие билетов нужно уточнить в кассе.
'''),
('e3_budget', 3, 'Comparing changes in a budget', [
('A', 'В отчёте отмечено повышение тарифов. Увеличение расходов на доставку обсудят отдельно.'),
('B', 'Что предлагают делать с поездками?'),
('A', 'Их число хотят сокращать. При этом число онлайн-встреч стало уменьшаться ещё осенью. Эти изменения нужно показать на разных графиках, чтобы не запутать читателей.')], '''
повышение|increase|повышение|an increase|a reduction;a freeze;a cancellation|What change in tariffs is reported?|Повышение цен заметили все покупатели.
увеличение|increase|Увеличение|an increase|a decrease;a postponement;a redistribution|What change in delivery expenses will be discussed?|Увеличение числа заявок нас удивило.
сокращать|to reduce|сокращать|reduce|increase;maintain;reschedule|What do the planners want to do with the number of trips?|Компания будет сокращать расходы на бумагу.
уменьшаться/уменьшиться|to decrease, to reduce|уменьшаться|decrease|increase;remain steady;fluctuate|What began happening to the number of online meetings in autumn?|К вечеру очередь начала уменьшаться.
'''),
('e3_diplomacy', 3, 'Preparing a briefing on a visit', [
('A', 'В программе визита указана встреча в ООН. Министр иностранных дел приедет туда утром.'),
('B', 'Кто подготовит материалы для журналистов?'),
('A', 'Наше представительство. После встречи намечен обмен документами. Точное время ещё уточняют, поэтому я пока не рассылаю окончательную программу.')], '''
ООН (Организация Объединённых Наций)|UN (the United Nations)|ООН|the United Nations|the European Union;the World Bank;the International Monetary Fund|Which organization is listed as the meeting location?|Заявление обсуждали в ООН.
министр иностранных дел|foreign minister|Министр иностранных дел|the foreign minister|the defense minister;the finance minister;the interior minister|Which official will arrive in the morning?|Министр иностранных дел ответил на вопросы.
представительство|representative office|представительство|representative office|news agency;travel agency;research institute|Who will prepare the press materials?|Представительство откроется в новом здании.
обмен|exchange|обмен|exchange|publication;destruction;translation|What is planned for the documents after the meeting?|Обмен книгами начнётся после занятия.
'''),
('e3_schedule', 2, 'Updating a work calendar', [
('A', 'Нужно наметить дату встречи. Очередной отчёт ещё не готов, поэтому лучше оставить время на проверку.'),
('B', 'В какой папке лежат материалы?'),
('A', 'Текущий список хранится у меня, а предыдущий я отправил в архив. Если тебе нужны оба, я попрошу прислать копию из старой папки.')], '''
намечать/наметить|to set, to schedule|наметить|schedule|cancel;confirm a past date;record the actual date|What needs to be done about the meeting date?|Мы хотим наметить маршрут заранее.
очередной (очередь 30)|next|Очередной|the next one|the first ever one;the final one;an extra unscheduled one|Which report is not ready yet?|Очередной выпуск выйдет в среду.
текущий|current|Текущий|current|draft;confidential;incomplete|Which list does the speaker have at hand?|Текущий план висит у входа.
предыдущий|preceding, previous|предыдущий|previous|revised;duplicate;approved|Which version of the list was sent to the archive?|Я перечитал предыдущий ответ.
'''),
('e3_forecast', 2, 'Deciding whether to keep an outdoor booking', [
('A', 'В прогнозе указана вероятность дождя. Организаторы обсуждают возможный перенос встречи в зал.'),
('B', 'Почему они так поздно вспомнили об этом?'),
('A', 'Прогноз изменился неожиданно. Несмотря на это, билеты пока остаются в продаже. Новое объявление обещали разместить сегодня вечером.')], '''
вероятность|probability|вероятность|probability|duration;intensity;starting time|Which aspect of rain is given in the forecast?|Вероятность ошибки здесь невелика.
возможный|possible|возможный|possible|compulsory;completed;prohibited|What is the status of moving the meeting indoors?|Это возможный вариант ответа.
неожиданно|unexpectedly, suddenly|неожиданно|unexpectedly|gradually;repeatedly;slightly|How did the forecast change?|Автобус неожиданно остановился.
несмотря на|despite|Несмотря на|despite|because of;before;instead of|How does the speaker connect the changed forecast with continued ticket sales?|Несмотря на усталость, мы продолжили работу.
'''),
('e3_industry', 2, 'Planning a regional interview', [
('A', 'На карте отмечены электростанция и шахта. Мы собираемся рассказать о них в следующем выпуске.'),
('B', 'С кем уже удалось договориться об интервью?'),
('A', 'Один шахтёр согласился встретиться после работы. Рядом есть частный музей, но туда мы пока не звонили. Сначала закончим список вопросов.')], '''
электростанция|power station|электростанция|a power station|a pumping station;a railway station;a radio station|Which facility is marked alongside the other industrial site?|Эта электростанция работает уже много лет.
шахта|mine|шахта|a mine|a factory;a warehouse;a quarry|What is the second industrial site marked on the map?|Шахта находится за посёлком.
шахтёр|miner|шахтёр|a miner|an electrician;a mechanic;a geologist|Who has agreed to an interview?|Шахтёр рассказал о своей работе.
частный|private|частный|private|municipal;state-run;university-run|How is the nearby museum’s ownership described?|В деревне открылся частный магазин.
'''),
('e3_town', 3, 'Preparing topics for a town forum', [
('A', 'Общественный совет собирает вопросы к встрече. Торговля будет одной из тем, но порядок выступлений ещё не определили.'),
('B', 'А что поручили нашей группе?'),
('A', 'Управление новым центром. Отдельно обсудят самоуправление. Нам нужно подготовить короткие заметки, чтобы участники могли прочитать их до начала.')], '''
общественный|public, social|Общественный|public|corporate;military;academic|What kind of council is collecting questions?|Общественный центр откроют весной.
торговля|trade, commerce|Торговля|commerce|transport;healthcare;construction|Which topic is explicitly listed for the meeting?|Торговля между городами постепенно растёт.
управление|management, administration|Управление|management|construction;financing;decoration|What aspect of the new center is assigned to the group?|Управление зданием требует опыта.
самоуправление|self-government|самоуправление|self-government|central control;privatization;foreign administration|What will be discussed separately?|Местное самоуправление стало темой урока.
'''),
('e3_celebration', 1, 'Planning a community event', [
('A', 'В воскресенье у нас праздник. Торжество начнётся в зале, а потом гости смогут выйти во двор.'),
('B', 'Как вы собираетесь отметить эту дату?'),
('A', 'Мы пригласили музыкантов. Присутствие бывших сотрудников особенно важно для организаторов. Им уже отправили письма, но ответили пока не все.')], '''
праздник|holiday|праздник|a holiday|a workday;a training day;an inspection day|What kind of day is Sunday for the speakers?|Этот праздник отмечают зимой.
торжество|celebration|Торжество|a celebration|a rehearsal;an election;a lecture|What will begin in the hall?|Торжество перенесли в большой зал.
отмечать/отметить|to mark, to celebrate|отметить|celebrate|postpone;forget;announce|What does the second speaker ask about doing with the date?|Мы хотим отметить годовщину дома.
присутствие|presence|Присутствие|presence|financial support;written advice;photographs|What is especially important regarding former employees?|Присутствие родителей на встрече приветствуется.
'''),
('e3_inquiry', 3, 'Checking the wording of a report', [
('A', 'Вывод в конце отчёта пока не изменили. Но появилось новое обстоятельство, которое нужно учесть.'),
('B', 'Что мы должны сделать до публикации?'),
('A', 'Определить время события. Согласно инструкции, эту строку нельзя оставлять пустой. Я позвоню автору и попрошу проверить записи ещё раз.')], '''
вывод|conclusion|Вывод|the conclusion|the quotation;the title;the signature|What part at the end of the report remains unchanged?|Вывод автора меня удивил.
обстоятельство|circumstance|обстоятельство|a circumstance|a regulation;a deadline;a request|What new element must be taken into account?|Это обстоятельство повлияло на решение.
определять/определить|to determine|Определить|determine|conceal;change;estimate roughly|What must be done regarding the event’s time?|Нужно определить причину задержки.
согласно|according to|Согласно|according to|contrary to;regardless of;in addition to|How does the speaker relate the rule to the instruction?|Согласно расписанию, поезд придёт вечером.
'''),
]
