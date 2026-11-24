"""Fourth ALES batch: fictional dialogues targeting 80 previously uncovered senses."""

SPECS = [
('e4_visit', 1, 'Remembering a visit', [
('A', 'Вчера мы успели побывать у Анны. Её супруг открыл дверь и пригласил нас в гостиную.'),
('B', 'Вы раньше встречались?'),
('A', 'Нет, но он сразу подошёл пожать руку. Благодаря Анне мы нашли общий язык очень быстро. Потом она показала нам фотографии и предложила чай.')], '''
побывать|to visit|побывать|visit|move in;work;stay overnight|What did the speakers manage to do at Anna’s home?|Я хочу побывать в этом музее.
супруг|spouse|супруг|husband|brother;father;neighbor|Who opened the door?|Её супруг работает в библиотеке.
пожимать/пожать руку|to shake hands|пожать руку|shake hands|give a hug;take a coat;offer a seat|What did the man approach the visitors to do?|После встречи я хотел пожать руку тренеру.
благодаря|because of, thanks to|Благодаря|thanks to|despite;instead of;without|How does the speaker describe Anna’s role in helping them get along?|Благодаря карте мы быстро нашли дом.
'''),
('e4_walk', 1, 'Planning a forest outing', [
('A', 'В программе завтра ходьба. Для неё выделили целый день, поэтому лучше взять еду с собой.'),
('B', 'Мы пойдём вдоль дороги?'),
('A', 'Нет, маршрут уходит вглубь леса. Когда начнём приближаться к озеру, сделаем остановку. Руководитель пришлёт карту сегодня вечером.')], '''
ходьба (ходить 11)|walk|ходьба|walking|running;cycling;climbing|What activity is on tomorrow’s program?|Быстрая ходьба помогает мне проснуться.
целый|whole, entire|целый|a whole day|half a day;an extra day;the following day|How much of the day has been allocated?|На дорогу ушёл целый день.
вглубь|deep into|вглубь|deeper into|along the edge of;around;away from|Where does the route lead relative to the forest?|Тропа ведёт вглубь долины.
приближаться (близко 6)|to draw near, to approach|приближаться|approach|leave;circle;cross|What will the group be doing in relation to the lake when it stops?|Поезд начал приближаться к станции.
'''),
('e4_chess', 1, 'Discussing a chess evening', [
('A', 'Наша партия закончилась поздно. Я выбрал смелый ход, хотя долго не мог решиться.'),
('B', 'Твой соперник удивился?'),
('A', 'Нет, у него был уверенный вид. В итоге мне удалось превзойти его результат в прошлом турнире. Завтра я попрошу тренера разобрать последние ходы.')], '''
партия|game|партия|a game|a political party;a team;a shipment|What finished late that evening?|Эта партия длилась почти час.
смелый|bold, courageous|смелый|bold|cautious;ordinary;forced|How does the speaker describe the chosen move?|Это смелый план для маленькой команды.
уверенный|sure, confident|уверенный|confident|confused;angry;exhausted|How did the opponent look?|У него был уверенный голос.
превосходить/превзойти|to exceed, to surpass|превзойти|surpass|equal;repeat;fall short of|What did the speaker manage to do relative to the opponent’s earlier result?|Она смогла превзойти собственный рекорд.
'''),
('e4_racing', 2, 'Preparing coverage of a sporting event', [
('A', 'Завтра начнутся гонки. Трасса уже готова, но журналистам пока не разрешают выходить на неё.'),
('B', 'Какие данные нужны для заметки?'),
('A', 'Средний результат участников и точность измерений. Организаторы обещали прислать таблицу. Без неё я не буду указывать числа в тексте.')], '''
гонки|races|гонки|races|practice sessions;qualifying interviews;award ceremonies|What starts tomorrow?|Гонки показали по телевидению.
трасса|route; path; road|Трасса|the course|the grandstand;the parking area;the equipment room|What is ready but still off limits to journalists?|Трасса проходит рядом с лесом.
средний|average, middle, mean|Средний|average|best;worst;latest|Which result statistic is needed?|Средний возраст группы — двадцать лет.
точность|precision|точность|precision|cost;frequency;duration|Which property of the measurements is requested?|Точность этого прибора проверяют каждый год.
'''),
('e4_panel', 2, 'Organizing a panel session', [
('A', 'Завтра будет выступать глава комиссии. Мы оставили для него время в начале программы.'),
('B', 'А кто ответит на вопросы после перерыва?'),
('A', 'Один член рабочей группы. Полный состав комиссии напечатают на отдельном листе. Этот лист раздадут всем у входа, чтобы не читать фамилии вслух.')], '''
выступать/выступить|to speak|выступать|speak|observe;translate;register|What will the official do tomorrow?|На открытии будет выступать наш преподаватель.
глава|head|глава|head|secretary;adviser;spokesperson|What position does the first scheduled person hold?|Глава делегации приехал вечером.
член|member|член|a member|a visitor;a critic;a sponsor|What is the question responder’s relationship to the working group?|Каждый член клуба получил письмо.
состав|composition|состав|membership|agenda;budget;history|What information about the commission will be printed separately?|Состав команды изменился в этом году.
'''),
('e4_options', 1, 'Choosing a plan for a group', [
('A', 'Я хочу предложить другой маршрут. Моё предложение уже лежит в общей папке.'),
('B', 'Когда нужно решить, какой вариант выбрать?'),
('A', 'До вечера. Я буду стараться закончить расчёты к обеду, чтобы у всех осталось время их посмотреть. Если увидишь ошибку, сразу напиши мне.')], '''
предлагать/предложить|to offer, to suggest, to propose|предложить|propose|reject;inspect;remember|What does the first speaker want to do with another route?|Можно предложить новую тему для встречи.
предложение|offer, suggestion; sentence|предложение|a suggestion|a sentence;a complaint;a contract|What is in the shared folder in this context?|Это предложение мы обсудим завтра.
решать/решить|to solve, to decide|решить|decide|announce;check;forget|What must the group do by evening?|Нам нужно решить, где встретиться.
стараться/постараться|to try, to attempt, to strive|стараться|try|refuse;pretend;be obliged|What attitude does the speaker express toward finishing the calculations?|Я буду стараться приходить вовремя.
'''),
('e4_design', 2, 'Planning a digital resource', [
('A', 'Мы решили создать электронный каталог. Его основу составят записи из старого архива.'),
('B', 'Кто будет разрабатывать программу?'),
('A', 'Небольшая команда из университета. Разработка займёт несколько месяцев. До этого нам нужно проверить названия и убрать повторяющиеся записи.')], '''
создавать/создать|to create|создать|create|sell;close;copy|What has the group decided to do with an electronic catalog?|Студенты хотят создать свой журнал.
основа|basis, foundation|основу|basis|appendix;exception;obstacle|What role will the old archive records play?|За основу взяли прошлогодний план.
разрабатывать/разработать|to develop|разрабатывать|develop|translate;advertise;purchase|What work on the software does the second speaker ask about?|Специалисты будут разрабатывать новый проект.
разработка|development|Разработка|development|delivery;training;maintenance|Which process will take several months?|Разработка устройства ещё не закончена.
'''),
('e4_machine', 2, 'Preparing a workshop demonstration', [
('A', 'В мастерскую привезли мощный станок. Это крупный заказ, и для него освободили место у стены.'),
('B', 'Когда его можно запускать?'),
('A', 'После проверки. Мы собираемся использовать его на занятиях, но сначала инженер объяснит правила. Пока я только фотографирую упаковку и записываю номер.')], '''
мощный|powerful|мощный|powerful|portable;quiet;inexpensive|What characteristic of the machine is mentioned?|Для этой работы нужен мощный насос.
крупный|large|крупный|large|urgent;unusual;overdue|How is the order described?|Это крупный проект для нашего отдела.
запускать/запустить|to launch|запускать|start up|unpack;move;return|What action involving the machine does the second speaker ask about?|Систему нельзя запускать без проверки.
использовать|to use|использовать|use|sell;store;replace|What do the speakers plan to do with the machine during lessons?|На уроке можно использовать словарь.
'''),
('e4_supplies', 2, 'Checking supplies for a school project', [
('A', 'Для занятий нужно закупить материалы. Количество указано в таблице, которую я прислал утром.'),
('B', 'Разве у нас ничего не осталось?'),
('A', 'Некоторые материалы имеются на складе. Остальное оплатят за счёт фонда. Я сначала сверю список, чтобы не заказать лишнего.')], '''
закупать/закупить (купить 17)|to purchase|закупить|purchase|borrow;distribute;return|What must be done with materials for the lessons?|Нужно закупить бумагу на весь месяц.
количество|number, quantity|Количество|quantity|supplier;price;delivery date|Which detail is given in the table?|Количество мест ограничено.
имеются|there are|имеются|are available|are ordered;are missing;are reserved|What is said about some materials at the warehouse?|В библиотеке имеются старые карты.
за счёт (счёт 23)|at the expense|за счёт|at the expense of|instead of;in addition to;without involving|How will the fund be involved in paying for the rest?|Поездку оплатили за счёт школы.
'''),
('e4_exhibit', 1, 'Choosing photographs for an exhibition', [
('A', 'Государственный музей прислал фотографии. Один местный художник помог выбрать снимки для нашего зала.'),
('B', 'Они относятся к новому проекту?'),
('A', 'Нет, это минувший сезон. Прежний организатор оставил подробные подписи. Я проверю их по каталогу, а потом передам дизайнеру.')], '''
государственный|national, state (attr.)|Государственный|state-run|privately owned;university-run;municipal|How is the museum described?|Государственный архив открыт по будням.
местный (место 13)|local|местный|local|foreign;famous;retired|How is the artist who helped described?|Местный житель показал нам дорогу.
минувший|last, past|минувший|past|coming;current;extended|Which season do the photographs represent?|В газете обсуждали минувший год.
прежний|former, previous|Прежний|previous|current;temporary;deputy|Which organizer left the captions?|Прежний владелец дома посадил этот сад.
'''),
('e4_restoration', 2, 'Discussing an old building', [
('A', 'Город хочет восстановить старый театр. Состояние здания описано в отчёте, который появился вчера.'),
('B', 'Работы проведут сразу во всех помещениях?'),
('A', 'Нет, план предусматривает постепенный переход от одного зала к другому. Часть росписи сохранилась, поэтому её сначала покажут специалистам.')], '''
восстанавливать/восстановить|to restore|восстановить|restore|demolish;sell;relocate|What does the city want to do with the theater?|Мастер обещал восстановить старую мебель.
состояние|condition|Состояние|condition|ownership;location;value|Which aspect of the building does the report describe?|Состояние дороги проверят утром.
постепенный|gradual|постепенный|gradual|immediate;temporary;unexpected|How is the transition between halls planned?|Нужен постепенный переход к новому расписанию.
сохраняться/сохраниться|to keep, to remain|сохранилась|has survived|has faded;has been copied;has been removed|What is said about part of the wall painting?|В архиве сохранилась старая фотография.
'''),
('e4_waterway', 2, 'Checking a river service notice', [
('A', 'В заметке говорится про сообщение между двумя городами. Корабль выйдет утром, если расписание не изменится.'),
('B', 'Это тот судоходный канал, который мы видели на карте?'),
('A', 'Да. Связь с диспетчером уже установили. Он обещал уточнить время вечером, поэтому билеты пока оставим у себя.')], '''
сообщение (между А и Б)|communication, connection|сообщение|transport connection|written announcement;radio signal;news article|What is the subject linking the two cities in this context?|Регулярное сообщение между островами возобновили.
корабль|ship, craft|Корабль|a ship|a train;a bus;an aircraft|What is scheduled to depart in the morning?|Корабль стоит у причала.
судоходный|shipping|судоходный|navigable|irrigation-only;underground;dried-up|What kind of canal does the second speaker refer to?|Этот судоходный канал открыли давно.
связь|connection, link, contact|Связь|contact|an agreement;a dispute;a meeting|What has already been established with the dispatcher?|Связь с островом восстановили вечером.
'''),
('e4_maritime', 3, 'Planning a museum interview', [
('A', 'Новый раздел музея называется «Оборона побережья». На первой фотографии — подводная лодка.'),
('B', 'Кто расскажет о коллекции?'),
('A', 'Военнослужащий, которого пригласили организаторы. Военно-морские силы передали музею часть материалов. Вопросы для интервью мы согласуем с ним завтра.')], '''
оборона|defense|Оборона|defense|exploration;settlement;trade|What is the new section’s theme concerning the coast?|Оборона города описана в этой книге.
подводная лодка (подлодка)|submarine|подводная лодка|a submarine|a destroyer;an aircraft carrier;a patrol boat|What appears in the first photograph?|Подводная лодка вернулась в порт.
военнослужащий|serviceman|Военнослужащий|a service member|a historian;a journalist;a civilian engineer|Who has been invited to discuss the collection?|Военнослужащий ответил на вопросы школьников.
военно-морские силы|navy|Военно-морские силы|the navy|the army;the air force;the border service|Which organization supplied some of the materials?|Военно-морские силы участвовали в выставке.
'''),
('e4_leadership', 3, 'Comparing political reports', [
('A', 'Власти опубликовали ответ на обращение жителей. В нём говорится, кому принадлежит власть в этом вопросе.'),
('B', 'А что известно о руководителе совета?'),
('A', 'Его отставка пока обсуждается. Он сам заявил, что готов уйти в отставку, но дату не назвал. Я проверю официальное сообщение перед выпуском.')], '''
власти (pl.)|authorities|Власти|the authorities|the residents;the journalists;the petitioners|Who published the response?|Власти сообщили об изменении правил.
власть (f.)|power|власть|authority|responsibility for costs;ownership of property;public support|What does the response clarify someone’s possession of in this matter?|Власть перешла к новому совету.
отставка|resignation|отставка|resignation|promotion;appointment;temporary leave|What change concerning the council leader is under discussion?|Его отставка стала темой заседания.
уходить/уйти в отставку|to resign|уйти в отставку|resign|stand for election;take a vacation;seek promotion|What did the leader say he was prepared to do?|Министр решил уйти в отставку.
'''),
('e4_court', 3, 'Reading a court report', [
('A', 'Судья закончил заседание. В статье сказано, что человека решили приговорить к двум годам заключения.'),
('B', 'Уточняется, куда его отправят?'),
('A', 'Указана тюрьма в соседнем районе. Других подробностей пока нет. Я попрошу редактора проверить формулировки, прежде чем мы перескажем эту новость.')], '''
судья|judge|Судья|the judge|the prosecutor;the defense lawyer;the witness|Who ended the hearing?|Судья попросил всех сесть.
приговорить|to sentence, to condemn|приговорить|sentence|question;acquit;release|What legal action was decided concerning the person?|Суд может приговорить его к штрафу.
заключение|imprisonment; conclusion|заключения|imprisonment|probation;community service;house arrest|What does the two-year term refer to in this report?|Три года заключения изменили его жизнь.
тюрьма|jail, prison|тюрьма|a prison|a courthouse;a police station;a hospital|What facility is named in the neighboring district?|Эта тюрьма находится за городом.
'''),
('e4_newsroom', 3, 'Checking attribution in a news brief', [
('A', 'По сообщениям прессы, встреча состоится завтра. Но у нас пока нет подтверждения из официального источника.'),
('B', 'А что говорится в документе на столе?'),
('A', 'Это заявление организаторов. Они хотят заявить о новом проекте, а подробности будут сообщать позже. Я отмечу эту разницу в тексте.')], '''
по сообщениям прессы (по 22)|according to the press reports|По сообщениям прессы|according to press reports|according to eyewitnesses;according to the organizer;according to an official schedule|What source is given for the meeting date?|По сообщениям прессы, дорогу откроют летом.
заявление|declaration|заявление|a statement|an invitation;a transcript;a contract|What kind of document is on the desk?|Заявление напечатали на первой странице.
заявлять/заявить|to declare, to announce|заявить|announce|ask questions;raise doubts;remain silent|What do the organizers intend to do regarding the new project?|Он хочет заявить о своём решении.
сообщать/сообщить|to report|сообщать|report|verify;withhold;discuss internally|What will they do with the details later?|Об изменениях будут сообщать по радио.
'''),
('e4_aircraft', 3, 'Preparing an aviation history segment', [
('A', 'В фильме показан сверхзвуковой самолёт. Во время испытаний он потерпел аварию, но пилот успел катапультироваться.'),
('B', 'А что в следующем эпизоде?'),
('A', 'Посадка другой машины. Эти кадры сняли позже, поэтому их нельзя ставить рядом без пояснения. Я добавлю даты под каждым эпизодом.')], '''
сверхзвуковой|supersonic|сверхзвуковой|supersonic|subsonic;unmanned;amphibious|What type of aircraft is shown in the first episode?|Этот сверхзвуковой самолёт находится в музее.
потерпеть аварию|to have an accident|потерпел аварию|had an accident|lost radio contact;changed course;made a test flight|What happened to the aircraft during testing?|Этот самолёт потерпел аварию много лет назад.
катапультироваться|to eject|катапультироваться|eject|land the aircraft;restore control;send a message|What did the pilot manage to do?|Пилот смог катапультироваться вовремя.
посадка|landing|Посадка|a landing|a takeoff;a refueling;a flyover|What appears in the later episode?|Посадка прошла без задержки.
'''),
('e4_fire_report', 2, 'Checking an incident summary', [
('A', 'В сводке написано, что пожар возник вечером. Огонь начал охватывать верхний этаж ещё до приезда помощи.'),
('B', 'Что известно о людях внутри?'),
('A', 'У одного человека ожог руки. Спасательный отряд передал эти сведения редакции. Имена пока не публикуют, а остальные данные ещё проверяют.')], '''
пожар возник|fire started|пожар возник|a fire started|a fire was detected;a fire was contained;a fire was extinguished|What event is placed in the evening?|В соседнем здании пожар возник ночью.
охватывать/охватить|to engulf, to envelop|охватывать|engulf|bypass;recede from;remain below|What did the fire begin doing to the upper floor?|Туман начал охватывать долину.
ожог|burn|ожог|a burn|a fracture;a bruise;a cut|What injury to a hand is reported?|У него остался небольшой ожог.
спасательный|rescue (attr.)|Спасательный|rescue|police;construction;medical research|What kind of team supplied the information?|Спасательный катер вернулся к берегу.
'''),
('e4_access', 2, 'Discussing access to an archive', [
('A', 'Защита документов — главная тема новой инструкции. Охрана уже получила свой экземпляр.'),
('B', 'Почему нам не разрешили войти вчера?'),
('A', 'В письме указано отсутствие разрешения. Отказ можно обжаловать, но сначала нужно выяснить, какого документа не хватает. Я позвоню в архив после обеда.')], '''
защита|protection|Защита|protection|translation;publication;replacement|What aspect of the documents is the instruction about?|Защита старых книг требует внимания.
охрана|guard, protection|Охрана|security staff|cleaning staff;research staff;visitors|Who already received a copy?|Охрана проверила вход.
отсутствие|absence, lack|отсутствие|absence|expiration;withdrawal;incorrect wording|What problem with permission is stated in the letter?|Отсутствие ответа нас удивило.
отказ|refusal|Отказ|a refusal|a fee;a delay;an appointment|What can be appealed?|Отказ пришёл по электронной почте.
'''),
('e4_town_project', 2, 'Discussing a community initiative', [
('A', 'В отчёте описана деятельность нашего центра. Развитие района выделили в отдельную главу.'),
('B', 'Чего организаторы ждут от нового проекта?'),
('A', 'Они надеются, что он будет способствовать сотрудничеству. Но без общего усилия результата не будет. Поэтому на следующую встречу пригласили всех участников.')], '''
деятельность|activity|деятельность|activities|location;ownership;expenses|What does the report describe about the center?|Его деятельность связана с образованием.
развитие|development|Развитие|development|boundaries;population;history|What aspect of the district has its own chapter?|Развитие транспорта обсуждали на встрече.
способствовать|to contribute|способствовать|contribute to|replace;prevent;require|What relationship do organizers hope the project will have to cooperation?|Новый маршрут будет способствовать обмену товарами.
усилие|effort|усилия|effort|funding;permission;leadership|What shared input does the speaker say is necessary for results?|Без дополнительного усилия задачу не решить.
'''),
]
