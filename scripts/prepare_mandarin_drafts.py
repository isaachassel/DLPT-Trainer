"""Rebuild original Mandarin practice drafts offline; never spends or approves audio.

Simplified Chinese; provisional ILR anchors, not calibrated official test items.
Questions store exact Chinese evidence in the schema's legacy evidence_ru field.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.constants import ILR_THETA
from core.models import GenerationMetadata, PassageItem, QuestionItem
from core.preset_bank import ContentItem, ContentPackage, ROOT, Turn, write_package
from core.validation import content_hash, target_unit_count, validate_passage, validate_question


def q(stem, answers, evidence, rationale, kind="prominent detail"):
    # Correct option first; the materializer rotates its displayed position.
    return stem, answers, evidence, rationale, kind


READING = [
    ("0", "Public services", "signage", "Read two signs in a building.",
     "入口。出口。", "Isolated high-frequency sign recognition at the model floor, not connected comprehension.", [
         q("What does the first sign indicate?", ["Entrance", "Kitchen", "Parking", "Office"], "入口", "The first sign identifies an entrance."),
         q("What does the second sign indicate?", ["Exit", "Elevator", "Reception", "Toilets"], "出口", "The second sign identifies an exit.")]),
    ("0", "Commerce", "labels", "Read two labels in a shop.",
     "牛奶。面包。", "Recognition of two familiar food words.", [
         q("Which item is named first?", ["Milk", "Juice", "Rice", "Tea"], "牛奶", "The first word means milk."),
         q("Which item is named second?", ["Bread", "Eggs", "Fish", "Apples"], "面包", "The second word means bread.")]),
    ("0+", "Daily life", "notice", "Read a short notice on a door.",
     "阅览室\n周一至周五：上午九点到下午五点。\n周六、周日：休息。\n地点：二楼。",
     "Formulaic hours and location with very common days, times and numbers.", [
         q("When does this room open on weekdays?", ["Nine in the morning", "Five in the morning", "Two in the afternoon", "Seven in the evening"], "上午九点", "The listed weekday opening time is nine in the morning."),
         q("Where is the room?", ["On the second floor", "On the first floor", "Beside the station", "Behind the school"], "地点：二楼", "The location line specifies the second floor.")]),
    ("0+", "Commerce", "advertisement", "Read a small printed advertisement.",
     "自行车出售。蓝色。一百元。电话：六二八五。晚上联系。",
     "A formulaic sale listing with isolated familiar details.", [
         q("What is offered for sale?", ["A bicycle", "A table", "A suitcase", "A telephone"], "自行车出售", "The listing offers a bicycle."),
         q("When should a buyer make contact?", ["In the evening", "Early in the morning", "At midday", "Only on Sunday"], "晚上联系", "The final instruction asks for evening contact.")]),
    ("1", "Daily life", "personal message", "Read a message left for a family member.",
     "小林，我今天下午去看奶奶，六点以前回来。饭在冰箱里，你热一下就能吃。桌上的苹果是给你的。请把阳台上的衣服收进来，今天可能下雨。狗已经吃过饭了，不用再喂。妈妈。",
     "Simple connected household sentences with explicit actions and a basic negative instruction.", [
         q("What does the writer ask Xiaolin to do?", ["Bring in the clothes", "Feed the dog again", "Buy some apples", "Visit a neighbor"], "请把阳台上的衣服收进来", "The direct request is to bring the clothes indoors."),
         q("Where is the prepared food?", ["In the refrigerator", "On the balcony", "Inside a schoolbag", "Beside the front door"], "饭在冰箱里", "The message places the food in the refrigerator.")]),
    ("1", "Transportation", "service notice", "Read a notice for bus passengers.",
     "今天学校门口修路，十二路公交车不停这一站。请到书店前面等车，从学校向右走五分钟就到。车票还是两元，可以在车上买。明天上午恢复原来的站点。",
     "Simple directions and an explicit temporary transport change.", [
         q("Where should passengers wait today?", ["In front of the bookshop", "Behind the school", "Inside the bus station", "Opposite the supermarket"], "请到书店前面等车", "The notice directs passengers to the bookshop."),
         q("When will the normal stop reopen?", ["Tomorrow morning", "This afternoon", "Next Friday", "Next month"], "明天上午恢复原来的站点", "The normal stop returns tomorrow morning.")]),
    ("1+", "Workplace", "email", "Read a message about a workplace event.",
     "各位同事：周五的设备培训改到周四下午三点，地点仍是二楼会议室。因为周五技术员要去外地安装设备，我们提前一天上课。已经报名的人不必重新登记。如果周四不能参加，请在明天中午以前回复邮件，我们会安排下周的补课。培训前请先看附件里的操作说明，但不要自己接通新设备的电源。现场练习由技术员指导。",
     "Routine work instructions with changed timing, a reason, a conditional alternative and a restriction.", [
         q("Why has the training been moved?", ["The technician must travel on Friday", "The meeting room is closed on Thursday", "The equipment will arrive next month", "Employees requested an evening class"], "周五技术员要去外地安装设备", "The technician's travel requires an earlier session.", "cause and effect"),
         q("What should someone unable to attend do?", ["Reply before tomorrow noon", "Register again on Friday", "Connect the equipment alone", "Wait outside the meeting room"], "请在明天中午以前回复邮件", "A timely reply allows a make-up session to be arranged.")]),
    ("1+", "Education", "course announcement", "Read an announcement about a community class.",
     "社区周末开设陶艺入门课，适合没有经验的成年人。第一节课学习做杯子，第二节课给作品上色。学员不用自带材料，但要穿不怕弄脏的衣服。网上报名后，请等工作人员发短信确认再付款。如果报名人数太少，课程会推迟一周。烧好的作品不能当天带走，需要在收到通知后到前台领取。",
     "Familiar course information requiring sequence and conditional instructions across sentences.", [
         q("What must applicants receive before paying?", ["A confirmation text message", "Their finished ceramic cup", "A set of painting materials", "A notice that the course is canceled"], "请等工作人员发短信确认再付款", "Payment follows the confirmation message.", "sequence"),
         q("When can learners collect their finished work?", ["After receiving a collection notice", "Before the first class begins", "At the end of the first lesson", "Immediately after registering online"], "需要在收到通知后到前台领取", "Firing takes time; collection follows a later notice.")]),
    ("2", "Public services", "local news", "Read a report about a neighborhood service.",
     "青河社区的便民食堂经过两个月改造，本周重新营业。过去，居民点餐后还要到另一处窗口付款，高峰时两条队伍经常挡住入口。这次食堂把点餐和结账合并到同一窗口，并在门口增设了当天菜单，方便居民排队前作出选择。\n\n改造期间，社区调查了老年居民的用餐需求。不少人希望能把晚饭带回家，因此食堂决定试行晚餐打包服务，领取时间为下午四点半到五点半。需要这项服务的居民应在当天上午十点前登记，工作人员据此安排备菜。堂食午餐的价格暂时不变，晚餐则按实际所选菜品收费。食堂负责人表示，试行一个月后，会根据每天剩余饭菜的数量和居民反馈调整备餐量，不会一开始就扩大配送范围。",
     "Factual report across past and future timeframes with procedure, concrete causes and evaluation details.", [
         q("What problem did combining the windows address?", ["Queues obstructing the entrance", "Residents losing their meal cards", "Suppliers delivering food too late", "Menus listing unavailable ingredients"], "两条队伍经常挡住入口", "The two queues previously obstructed access.", "cause and effect"),
         q("What must residents do to obtain a takeaway dinner?", ["Register before ten that morning", "Reserve a table the previous week", "Pay a fixed monthly delivery fee", "Collect a ticket after the lunch service"], "应在当天上午十点前登记", "Morning registration lets the staff plan preparation."),
         q("What will guide changes in meal quantities?", ["Leftovers and feedback during the trial", "The length of the earlier renovation", "The number of windows in the building", "Delivery charges in neighboring towns"], "每天剩余饭菜的数量和居民反馈", "The manager names leftovers and residents' feedback as evidence.")]),
    ("2", "Environment", "project report", "Read a report about rainwater collection.",
     "去年夏天，明湖小学在两栋教学楼旁安装了雨水收集箱，准备用收集的水浇花。刚开始，箱口没有过滤网，树叶经常堵住水管。学校后来加装了过滤装置，并安排值班人员每周清理，堵塞情况才明显减少。\n\n今年，负责老师把日常记录交给科学兴趣小组。学生只负责观察水位和填写表格，设备检查仍由成年人完成。连续晴天时，收集箱中的水不够用，学校就减少草坪浇水，把有限的水优先用于新栽的树苗。校方准备在学期末比较安装前后的自来水用量。不过老师提醒，降雨多少和绿化面积的变化也会影响结果，不能把所有节水量都算成设备的功劳。是否增加收集箱，要等这次比较完成后再决定。",
     "Concrete project history, division of tasks, resource priorities and explicitly qualified interpretation.", [
         q("What reduced the pipe blockages?", ["Adding filters and regular cleaning", "Replacing the school science group", "Removing all plants from the grounds", "Recording water levels twice a day"], "加装了过滤装置，并安排值班人员每周清理", "Filters and cleaning addressed the leaf blockages.", "cause and effect"),
         q("What receives priority when collected water is limited?", ["Newly planted trees", "The entire lawn", "Classroom floors", "The sports field"], "优先用于新栽的树苗", "The school prioritizes new trees."),
         q("Why should water-use comparisons be interpreted cautiously?", ["Rainfall and planted area can also change", "Students are forbidden to record water levels", "The filters have never been installed", "The school has already removed the tanks"], "降雨多少和绿化面积的变化也会影响结果", "Other changing factors can affect the measured savings.", "cause and effect")]),
    ("2+", "Culture and society", "commentary", "Read a commentary about a museum policy.",
     "一家地方博物馆宣布取消门票后，参观人数明显增加，有人据此断言，免费就是让文化走近公众的最好办法。这项变化当然值得欢迎：对一家几口同时出门的家庭来说，省下门票确实减轻了负担。但走进大门，只是接近文化资源的第一步。\n\n如果展厅说明依然充满专业术语，讲解活动总在工作日白天举行，那么增加的可能只是进门的人数，而不是愿意停留、能够理解的观众。反过来，也不能因为部分人只是拍照，就认定免费吸引来的都是不认真的参观者。一次偶然的到访，可能成为持续兴趣的起点。\n\n与其急着给免费政策打满分或判失败，不如跟踪不同人群的参观经历：第一次来的家庭是否还会回来，年长观众能否看清说明，附近上班的人有没有合适的活动时间。把这些细节补上，比单纯追求客流纪录更能说明公共投入的价值。门打开了，还需要把通往展品的路修好。",
     "Qualified argument, alternative interpretations and a metaphor linking formal access to meaningful participation.", [
         q("What is the main limitation of using visitor numbers alone?", ["They do not show whether visitors can engage with the exhibits", "They establish that charging admission improves understanding", "They reveal which professional terms every visitor already knows", "They prove that all first-time visitors will become regulars"], "增加的可能只是进门的人数", "Admission counts do not measure comprehension or engagement.", "inference"),
         q("Why does the author discuss visitors who only take photographs?", ["To resist dismissing an initial visit as worthless", "To recommend prohibiting cameras in all galleries", "To argue that guided tours should replace exhibitions", "To explain why museums must restore their entrance fees"], "可能成为持续兴趣的起点", "A casual first visit can lead to later interest.", "speaker/writer intent"),
         q("What does repairing the route to the exhibits represent?", ["Removing practical barriers to meaningful access", "Replacing every damaged floor inside the museum", "Building a new road from the nearest railway station", "Moving the collection to a more expensive building"], "门打开了，还需要把通往展品的路修好", "The metaphor refers to understandable explanations and usable schedules.", "meaning from context")]),
    ("2+", "Workplace", "opinion column", "Read a column about flexible working hours.",
     "公司试行弹性上班后，迟到记录减少，管理层很快宣布制度取得成功。员工却有不同感受：有人能避开早高峰，也有人发现，同事上下班时间不同，自己反而更难结束一天的工作。早到的人希望清晨就得到回复，晚到的人又在傍晚发来任务，表面自由的时间被拉成了一根更长的线。\n\n问题未必出在弹性本身。如果团队预先约定共同协作的时段，并明确什么事情可以等到第二天，个人选择和集体配合并不矛盾。真正需要警惕的是，单位把协调责任全部交给个人，却仍按随时在线来判断投入程度。这样一来，不愿让家庭时间被打断的人，可能反而被看作不够积极。\n\n试行结果应同时观察工作交付和员工可支配的时间。减少迟到只是一个容易统计的变化，不能替代对制度目标的讨论。弹性安排要让人能够规划生活，而不是让工作学会绕过时钟。",
     "Competing experiences, a conditional remedy and inference about informal evaluation incentives.", [
         q("Why might flexible hours lengthen someone's effective workday?", ["Different colleagues expect responses at different times", "The company requires every worker to use the same train", "Employees must record their arrival twice each morning", "The new policy prohibits leaving before the manager arrives"], "早到的人希望清晨就得到回复，晚到的人又在傍晚发来任务", "Staggered expectations can stretch the period of availability.", "cause and effect"),
         q("Which practice would undermine the policy's purpose?", ["Judging commitment by constant online availability", "Agreeing on hours when colleagues work together", "Allowing routine requests to wait until tomorrow", "Considering whether employees can plan personal time"], "按随时在线来判断投入程度", "Constant availability pressures staff to surrender the time flexibility should protect.", "inference"),
         q("What does the final image of work bypassing the clock imply?", ["Work demands can spread beyond recognizable boundaries", "Flexible workers can complete every task more quickly", "Offices should remove clocks to encourage creativity", "Managers need newer software to record daily attendance"], "不是让工作学会绕过时钟", "The image warns against work expanding into all personal time.", "meaning from context")]),
    ("3", "Government and politics", "editorial", "Read an editorial about the publication of administrative data.",
     "某市将各部门的办事数据集中到公开平台，访问量迅速上升，宣传材料便把它称为监督方式的一次突破。公开当然比封闭前进了一步，但如果监督的成本只是从掌握数据的机构转移给不熟悉统计口径的市民，透明就可能停留在形式上。人们看得见数字，却未必知道它回答了什么问题。\n\n例如，一张表显示某项申请的平均办理时间缩短了，却没有说明未获受理的申请是否进入统计。若流程改革只是把审查移到正式受理之前，表上的速度可以提高，申请人的等待却未必减少。这不一定意味着工作人员故意隐瞒；不同部门沿用不同定义，也足以让一组真实数字拼成一幅失真的图景。\n\n有人担心，要求公布统计口径、缺失记录和修订理由，会给基层增加难以承受的负担。这个顾虑不能轻轻带过。与其要求每个窗口随时解释全部数据，不如在制度设计时确定共同标准，把说明作为发布的一部分，并保留公众提出具体疑问的渠道。否则，机构享有选择展示内容的便利，公众却承担解释错误的责任。\n\n当然，再完善的平台也不能替代调查，更不能保证每一种质疑都有道理。但承认解释可能出错，不应成为拒绝解释的理由。开放数据的价值，不在于把决定包装成已经被数字证明的事实，而在于让决定所依赖的判断有机会受到检验。一个能够承认并修正口径的平台，未必显得整齐，却比永远没有争议的展示墙更接近监督的本意。",
     "Sustained supported opinion with alternative explanations, concession, institutional asymmetry and a distinction between visible data and contestable judgment.", [
         q("What does the processing-time example demonstrate?", ["A favorable metric can coexist with an unchanged user experience", "Earlier screening necessarily makes applications legally invalid", "Public statistics are useful only when every applicant succeeds", "Shorter waiting times always require additional office staff"], "表上的速度可以提高，申请人的等待却未必减少", "Changing which interval is measured can improve the metric without reducing total waiting.", "inference"),
         q("How does the author respond to concerns about administrative burden?", ["By accepting the concern and proposing standards built into publication", "By treating every objection as evidence of deliberate concealment", "By requiring each clerk to explain all records whenever asked", "By suggesting that agencies stop publishing disputed figures"], "在制度设计时确定共同标准，把说明作为发布的一部分", "The proposed response integrates explanation into the process rather than dismissing workload.", "relationship of ideas"),
         q("Why might a less tidy platform better serve oversight?", ["Visible corrections can expose the judgments behind official claims", "Removing inconsistent records guarantees that all decisions are fair", "Unresolved complaints make numerical evidence unnecessary", "Fewer published tables necessarily reduce the public's workload"], "让决定所依赖的判断有机会受到检验", "Revisability and scrutiny matter more than an appearance of uncontested certainty.", "inference")]),
    ("3", "Culture and society", "opinion essay", "Read an essay about preserving a changing neighborhood.",
     "老街改造方案公布后，支持者强调修复屋顶、埋设管线和恢复街面风貌，反对者则担心原有商户被统一招商取代。双方都在谈保护，却未必在保护同一种东西：前者关注可辨认的建筑形象，后者在意使这些建筑成为生活场所的关系。若不把这一差别说清楚，讨论很容易变成谁更热爱历史的表态比赛。\n\n建筑安全不能因怀旧而被搁置，经营者也没有理由要求街区永远不变。但把所有店面整修得像同一时期的照片，同样不能保证历史得以延续。一家修伞铺的招牌也许不够古朴，店主积累的熟客关系却无法随外墙一起复制。反过来，也不应把每一项旧做法都当成不可触碰的传统，否则改善居住条件的居民倒成了破坏者。\n\n有人主张，先让项目通过商业运营实现收支平衡，再用收益扶持原有业态。这在账面上有吸引力，却把能否留下的问题推迟到了人已经离开以后。一旦租金结构和客流对象发生变化，后来发放补贴也未必能重建原先的日常联系。因此，保留低租金空间、允许分阶段修缮，不只是对效率的让步，也可能是避免失去不可逆资源的一种投资。\n\n这并不意味着所有老商户都必须留下，或者新经营者天然不属于这里。真正应讨论的是，谁有机会参与决定变化的速度，谁承担等待的成本。如果所谓保护，只允许过去以适合游客观看的样子存在，那么街区保住的可能是历史的布景，而不是继续生成历史的能力。好的改造应当容纳新的生活，也为尚未准备好离开的人保留谈判的余地。",
     "Abstract argument about preservation, irreversibility and competing values, with concessions on both sides and implied consequences of sequencing.", [
         q("What disagreement lies beneath the shared language of preservation?", ["Whether priority goes to visible form or continuing social relationships", "Whether all roofs need repair before any safety inspection occurs", "Whether new businesses can ever operate in a historic district", "Whether tourists should be required to visit with a local guide"], "前者关注可辨认的建筑形象，后者在意使这些建筑成为生活场所的关系", "The two sides attach different meanings to what should be preserved.", "relationship of ideas"),
         q("Why does the author question offering support only after commercial success?", ["Displacement may destroy relationships that later funding cannot restore", "Future subsidies would necessarily cost more than repairing every roof", "All original businesses would refuse to accept any financial assistance", "The project cannot collect rent until every local resident has departed"], "后来发放补贴也未必能重建原先的日常联系", "Delaying support risks losses that money cannot simply reverse.", "inference"),
         q("What does the distinction between a historical set and making history suggest?", ["Preservation should retain people's capacity to shape an evolving place", "A neighborhood should recreate one fixed era as accurately as possible", "Residents should abandon familiar businesses to attract more tourists", "Building safety matters only when old shops remain commercially viable"], "不是继续生成历史的能力", "The author values continuing agency and lived change over a static display.", "meaning from context")]),
]

LISTENING = [
    ("0", "Commerce", "word recognition", "Listen to two drink names.",
     ["牛奶。", "咖啡。"], "Isolated familiar word recognition at the model floor; not a functional proficiency claim.", [
         q("Which drink is named first?", ["Milk", "Water", "Coffee", "Juice"], "牛奶", "The first speaker says milk."),
         q("Which drink is named second?", ["Coffee", "Tea", "Milk", "Juice"], "咖啡", "The second speaker says coffee.")]),
    ("0", "Daily life", "word recognition", "Listen to two day words.",
     ["今天。", "明天。"], "Recognition of isolated high-frequency time words.", [
         q("Which day does the first word mean?", ["Today", "Yesterday", "Tomorrow", "Monday"], "今天", "The first word means today."),
         q("Which day does the second word mean?", ["Tomorrow", "Yesterday", "Today", "Friday"], "明天", "The second word means tomorrow.")]),
    ("0+", "Commerce", "short exchange", "Listen to a brief exchange at a shop.",
     ["您好！一杯咖啡，多少钱？", "十五元。", "谢谢。一杯咖啡。", "好的。"],
     "A formulaic purchase with a familiar item and explicit price.", [
         q("What does the customer want?", ["A cup of coffee", "A bottle of water", "A glass of milk", "A bowl of soup"], "一杯咖啡", "The customer requests coffee."),
         q("What is the stated price?", ["Fifteen yuan", "Fifty yuan", "Five yuan", "Twenty yuan"], "十五元", "The shopkeeper states fifteen yuan.")]),
    ("0+", "Public services", "short exchange", "Listen to a short exchange in a building.",
     ["请问，洗手间在哪里？", "在一楼，左边。", "一楼，左边。谢谢！", "不客气。"],
     "Formulaic location request and a repeated simple direction.", [
         q("What is the first speaker looking for?", ["The restroom", "The ticket office", "The dining room", "The elevator"], "洗手间在哪里", "The question asks where the restroom is."),
         q("On which floor is it?", ["The first floor", "The second floor", "The third floor", "The fourth floor"], "在一楼", "The response explicitly identifies the first floor.")]),
    ("1", "Daily life", "conversation", "Listen to two people arranging to meet.",
     ["小王，我们下午去公园，好吗？", "好啊。几点见？", "三点吧。我先去买水果，然后到公园东门等你。", "我坐公交车去，可能晚十分钟。你在门口的商店里等我，好不好？", "好，我带一把伞。今天可能下雨。", "那我带两瓶水。"],
     "Simple plans in familiar vocabulary with explicitly stated time and meeting location.", [
         q("Where will the first speaker wait?", ["In the shop at the park entrance", "At the bus stop behind the school", "Beside the lake in the park", "In the fruit market across town"], "在门口的商店里等我", "They agree to wait in the shop by the entrance."),
         q("What will Xiaowang bring?", ["Two bottles of water", "A bag of fruit", "An umbrella", "A bus timetable"], "那我带两瓶水", "Xiaowang offers to bring water.")]),
    ("1", "Commerce", "service conversation", "Listen to a customer speaking with a shop worker.",
     ["你好，我昨天买了这件衬衫，回家试了一下，有点小。", "您想换大一号的吗？", "对，还要白色的。", "白色的大号今天没有，明天下午能到。您可以先把这件带回去。", "那我明天下班后再来。需要带什么？", "把衬衫和购物小票一起带来就可以。"],
     "A routine purchase exchange requiring explicit size, timing and document details.", [
         q("Why does the customer want to exchange the shirt?", ["It is too small", "It is the wrong color", "It has a torn sleeve", "It arrived too late"], "有点小", "The customer says the shirt is a little small."),
         q("What should the customer bring with the shirt?", ["The purchase receipt", "A passport photograph", "A bank statement", "A written repair request"], "衬衫和购物小票一起带来", "The worker requests the shirt and receipt.")]),
    ("1+", "Workplace", "conversation", "Listen to colleagues discussing a delivery.",
     ["明天的资料已经装箱了，要不要现在送到培训中心？", "先别送。原来的教室漏水，培训改到隔壁的图书馆了。", "那我把新地址告诉司机。还是上午九点送到吗？", "对，不过图书馆九点才开门，你让司机九点十分到侧门，管理员在那里接货。", "打印的日程表还是旧地址，来不及全部重印了。", "没关系，在首页贴上更正通知。今天先把电子版发给参加培训的人，免得他们明天走错。"],
     "Routine coordination with a changed venue, delivery condition and prioritized corrective actions.", [
         q("Why has the training location changed?", ["The original classroom has a leak", "The driver cannot find the old address", "The library has canceled another event", "The participants requested a larger room"], "原来的教室漏水", "A leak made the original classroom unsuitable.", "cause and effect"),
         q("What should be done today to prevent confusion?", ["Send participants the electronic schedule", "Reprint every page of the paper schedule", "Leave the boxes outside the closed library", "Ask participants to collect materials early"], "今天先把电子版发给参加培训的人", "Sending the updated electronic version now helps prevent wrong arrivals.", "sequence")]),
    ("1+", "Transportation", "service conversation", "Listen to a traveler speaking with a station employee.",
     ["我买了明天上午的票，想改到今天晚上，还能改吗？", "今天晚上有一班车，不过只剩靠过道的座位。您原来的票可以改，差价需要补交。", "没问题。我的行李已经寄存了，改票后可以直接上车吗？", "不行，行李要先取出来，带着一起过安检。寄存处七点关门，您的车七点四十分开。", "那我先去取行李，再回来办改票。", "先在这里改好吧，不然座位可能卖完。取行李时出示寄存凭条就行，不用再排售票队。"],
     "Familiar travel transaction with ordered steps, closing time and a seat-availability condition.", [
         q("Why does the employee recommend changing the ticket first?", ["The remaining seat might be sold", "The luggage desk requires a new ticket", "Security checks end before seven", "The traveler has already missed the train"], "不然座位可能卖完", "The recommendation protects the remaining seat.", "cause and effect"),
         q("What must the traveler do before passing through security?", ["Retrieve the stored luggage", "Buy a new luggage allowance", "Return the original seat cushion", "Wait for the ticket counter to close"], "行李要先取出来，带着一起过安检", "The luggage must be collected and brought through security.", "sequence")]),
    ("2", "Public services", "interview", "Listen to an interview about a community repair service.",
     ["社区的旧物维修活动已经办了三个月。现在每次都有很多人来，最初也是这样吗？",
      "不是。第一次没有预约，大家同时带着东西来，志愿者根本忙不过来。有些人拿来大型冰箱，我们现场没有工具，也没办法修。后来改成提前登记，只接收台灯、电风扇这类小家电。",
      "登记时就能知道要花多少钱吗？",
      "检查不收费。需要更换零件的，我们先说明价格，居民同意后再修。买不到零件的，也会告诉对方原因，不会为了完成数量勉强维修。",
      "听说下个月还要增加一个环节？",
      "对，维修结束后安排半小时，教居民做简单的日常检查，比如清理外壳和查看电线有没有破损。涉及内部电路的，还是交给专业人员。我们希望减少可避免的小故障，而不只是等东西坏了再来。"],
     "Concrete service history, eligibility, fees and a future preventive activity.", [
         q("Why was advance registration introduced?", ["Too many people arrived together at the first event", "Volunteers wanted to sell larger household appliances", "Residents refused to pay the existing inspection fee", "The community center had lost its storage building"], "大家同时带着东西来，志愿者根本忙不过来", "Unmanaged arrivals overwhelmed the volunteers.", "cause and effect"),
         q("When will staff replace a part that costs money?", ["After the resident agrees to the quoted price", "Before informing the resident of the diagnosis", "Only after the resident buys a new appliance", "Whenever the monthly repair target is not met"], "居民同意后再修", "The price is explained and the resident agrees first."),
         q("What is the purpose of the new final activity?", ["Help residents prevent simple avoidable faults", "Train every resident to repair internal circuits", "Teach volunteers how to operate the booking system", "Persuade residents to replace all older appliances"], "减少可避免的小故障", "The practical instruction aims to prevent minor faults.", "speaker/writer intent")]),
    ("2", "Environment", "interview", "Listen to a discussion of a neighborhood flood-prevention project.",
     ["去年雨季，这一片停车场经常积水。今年铺了能透水的地砖，情况怎么样？",
      "普通降雨后，积水消退得比以前快。以前雨水都流向一个排水口，树叶一堵就很麻烦。现在一部分水能从地面渗下去，但遇到持续暴雨，仍然要靠排水管网。",
      "那是不是可以减少清理排水口的次数？",
      "恰恰不能这么理解。透水地砖不是替代管道，两套设施都得维护。施工时我们还保留了原来的检查口，方便工人清理。",
      "附近几个小区也想照着做，需要注意什么？",
      "先看地下条件。有的小区下面就是车库，不能直接照搬。我们的记录包括降雨量和积水持续时间，下半年会把结果交给区里，再决定哪些地方适合推广。只看雨后地面干不干，还不足以判断工程效果。"],
     "Factual infrastructure explanation, maintenance distinction and conditions for replication.", [
         q("What improvement has been observed during ordinary rain?", ["Standing water clears faster than before", "The drainage pipes no longer require maintenance", "No water ever reaches the existing outlet", "Every nearby garage now remains completely dry"], "积水消退得比以前快", "The observed improvement is faster drainage after normal rain."),
         q("How does the speaker describe the new paving's role?", ["It complements rather than replaces the pipes", "It makes inspection openings unnecessary", "It works only when every drain is blocked", "It eliminates the need to measure rainfall"], "透水地砖不是替代管道", "Both paving and drainage pipes continue to be needed.", "relationship of ideas"),
         q("What must other neighborhoods examine before copying the project?", ["The conditions underneath their paved areas", "The number of residents attending local meetings", "The price of parking permits in other districts", "The age of vehicles using their parking spaces"], "先看地下条件", "Underground garages and other site conditions may rule out direct replication.")]),
    ("2+", "Education", "discussion", "Listen to a discussion about an online course.",
     ["学校的新在线课程完成率很高，负责人说，说明学生特别喜欢这种学习方式。你怎么看？",
      "完成率是个好消息，但要先弄清楚完成指什么。如果系统只记录视频有没有播放到最后，学生可能一边做别的事一边让它播。数字是真的，解释却未必只有一种。",
      "那改成每看完一段就做题，是不是就可靠了？",
      "会多一些信息，但也可能把学习变成寻找标准答案。关键还要看学生能不能用学到的办法解决新问题。可以过一段时间再给一个不同的任务，而不是只重复视频里的例子。",
      "这样评估太慢，学校总得及时决定要不要续费吧？",
      "可以先续一个短周期，同时保留线下答疑，观察哪些学生真正受益。也别只访问顺利完成的人，中途退出的人可能不是不努力，而是家里没有安静的地方。我们不能把平台容易记录的东西，当成教育唯一值得在意的东西。"],
     "Qualified evaluation of a metric, competing explanations, a practical compromise and implied access barriers.", [
         q("What concern does the speaker raise about course completion?", ["The recorded behavior may not demonstrate actual learning", "The platform always loses its records before evaluation", "Students are forbidden to pause the instructional videos", "Every completed course must be repeated in a classroom"], "一边做别的事一边让它播", "Reaching the end of a video can occur without attention or learning.", "inference"),
         q("Why propose a different task after some time has passed?", ["To check whether learning transfers beyond remembered examples", "To postpone the subscription decision until all records disappear", "To ensure students can reproduce the video's wording exactly", "To replace all opportunities for asking questions in person"], "解决新问题", "A later new task tests usable learning rather than immediate recall.", "speaker/writer intent"),
         q("What does the example of a noisy home suggest?", ["Dropout may reflect learning conditions rather than lack of effort", "Students who leave early are always more capable than completers", "The school should stop interviewing students about their experience", "A higher completion rate requires making every assignment easier"], "可能不是不努力，而是家里没有安静的地方", "Material learning conditions offer an alternative explanation for withdrawal.", "inference")]),
    ("2+", "Commerce", "discussion", "Listen to two people discussing a service trial.",
     ["这家维修店试行上门取送后，订单多了三成。老板打算把范围扩大到整个城区，你觉得合适吗？",
      "先别只看订单。我们接触的几家店，距离一远，师傅花在路上的时间就增加，店里等维修的人反而更多。服务方便了新顾客，也可能让原来的顾客等得更久。",
      "多收一点取送费，能不能解决？",
      "能补一部分成本，但不一定补得回时间。可以把相邻街区的取件集中在固定时段，先试一条路线。顾客预约前要知道大概多久修好，不能只宣传免费上门。",
      "可固定时段不如随叫随到有吸引力。",
      "是啊，承诺少一点，广告上可能吃亏。但修东西最怕的不是晚半天，而是一直不知道还要等多久。把范围画得很大，却没有兑现承诺的能力，就像把门面撑大了，里面的架子却没加。试点应该证明服务接得住，而不是电话响得多。"],
     "Practical tradeoffs, distinction between money and capacity, qualified recommendation and service-capacity metaphor.", [
         q("What problem could accompany the increase in orders?", ["Travel time could slow repairs for existing customers", "Repair workers could lose access to all necessary tools", "Customers could become legally unable to collect their goods", "The shop could be required to stop charging for every repair"], "店里等维修的人反而更多", "More travel can reduce workshop capacity and increase waiting.", "inference"),
         q("Why might a higher pickup fee be insufficient?", ["Extra revenue does not necessarily restore workers' time", "Customers are prohibited from paying transport charges", "The shop has already recovered every operating expense", "All repair jobs require exactly the same amount of labor"], "不一定补得回时间", "Money can cover costs without supplying additional working time.", "cause and effect"),
         q("What does the larger storefront with unchanged shelves illustrate?", ["Advertised reach can exceed the capacity to fulfill promises", "The shop needs more attractive displays to sell its spare parts", "A larger building always lowers the cost of serving customers", "Existing customers prefer seeing repaired goods arranged neatly"], "把门面撑大了，里面的架子却没加", "The metaphor warns against expanding promises without operational support.", "meaning from context")]),
    ("3", "Government and politics", "interview", "Listen to an interview about how public projects are evaluated.",
     ["几个街道都推出了居民议事会，参加人数和建议数量增长很快。有人认为，这已经说明居民参与更充分了。您为什么还主张检查建议后来的去向？",
      "因为表达的机会和影响决定的机会，并不是一回事。如果居民每次都能发言，却始终不知道建议为什么被采纳或搁置，议事会就可能成为一个收集意见的容器，而不是共同判断的过程。数量增加值得肯定，但不能自动证明决定变得更开放。",
      "可有些建议涉及预算和安全，普通居民未必掌握全部情况。难道每个专业判断都要重新表决吗？",
      "当然不需要。专业人员有责任说明哪些限制不能回避，也有责任区分技术上做不到和现阶段不愿优先做。把两者都说成不可行，表面上节省了解释时间，实际上取消了讨论优先次序的空间。居民不必替工程师算承重，但有权知道为什么同样有限的资金先用于一处，而不是另一处。",
      "如果公开这些分歧，会议会不会更难达成共识，甚至让人觉得以前的工作都不可信？",
      "短期内可能更难看，尤其是过去习惯只公布一致意见的时候。但没有被说出来的分歧，并不等于不存在。若为了保持场面和谐而过滤掉异议，最终得到的只是无人反对的记录，未必是能够执行的决定。关键是设定回应期限，说明谁负责下一步，并允许后来出现的新证据改变原有安排。参与的价值不在于把每个人都变成赞成者，而在于让不同意见有一条可以追踪的路径。"],
     "Extended supported argument distinguishing voice from influence, expertise from priority setting, with concessions and institutional inference.", [
         q("Why does the interviewee want to trace the fate of suggestions?", ["Speaking opportunities alone do not establish influence over decisions", "Residents should replace experts in every technical calculation", "A larger number of comments makes all budgeting rules irrelevant", "Public meetings are worthwhile only when every proposal is funded"], "表达的机会和影响决定的机会，并不是一回事", "Following responses shows whether participation can affect decisions.", "inference"),
         q("Which distinction does the interviewee want professionals to explain?", ["Technical impossibility versus a choice about current priorities", "Formal meeting attendance versus registration on a mailing list", "Private construction expenses versus the price of public transport", "Past engineering calculations versus future architectural styles"], "技术上做不到和现阶段不愿优先做", "Professional constraints should not conceal discretionary priorities.", "relationship of ideas"),
         q("What is implied by a record showing that nobody objected?", ["It may conceal disagreement rather than demonstrate workable agreement", "It proves that every resident understood all technical evidence", "It obliges the authorities to fund the project without further review", "It means that no future evidence could justify revising the decision"], "只是无人反对的记录，未必是能够执行的决定", "A tidy record can be produced by filtering disagreement rather than resolving it.", "inference")]),
    ("3", "Science and technology", "interview", "Listen to a discussion about digitizing an archive.",
     ["地方档案馆把一批旧资料放到了网上，检索次数明显上升。项目负责人说，这让更多人有机会重新认识地方历史。您同意吗？",
      "总体上同意，但需要问哪些资料先被数字化。容易扫描、目录完整的文件通常最先上线，保存破损、说明不全的材料反而可能长期留在库房。用户检索不到它们，很容易把网上可见的部分当成过去的全部。技术扩大了入口，也可能在不知不觉中重新画定边界。",
      "可资金有限，总要有个先后顺序。先做最容易完成的部分，不是很合理吗？",
      "作为工作安排，这很合理。问题在于安排一旦变成看不见的筛选，暂时的先后就可能被误认成历史本身的重要程度。比如某个行业的资料整理得好，在平台上显得格外丰富；另一个行业的记录分散，研究者就可能以为它在当地从来不重要。后来发表的文章又主要引用前一批资料，原来的偏差便获得了新的权威。",
      "那是不是应该等全部整理完，再统一公开，免得误导使用者？",
      "那样可能让公众多年都用不上已经整理好的资源。我更赞成边开放边说明缺口：标明收录范围、选择原则和待处理部分，并让使用者补充线索。当然，补充内容还需要核实，不能因为来自公众就直接当成事实。我们要避免的不是所有不完整，而是把不完整包装成完整。一个愿意展示自身盲区的平台，可能比一个看起来无所不包的平台，更能支持严肃的研究。"],
     "Abstract argument about selection bias and self-reinforcing authority, with a rejected all-or-nothing alternative and qualified remedy.", [
         q("What unintended effect of digitization concerns the speaker?", ["Easily published material may appear to represent the entire past", "All damaged documents become impossible to preserve once scanned", "Greater public access necessarily prevents any new historical research", "Online searching removes every distinction between different industries"], "把网上可见的部分当成过去的全部", "Visibility depends partly on processing choices, not historical completeness.", "inference"),
         q("How can the initial imbalance acquire further authority?", ["Later scholarship may repeatedly cite the already visible material", "Archivists may be forced to digitize all industries simultaneously", "Readers may stop using the internet as soon as gaps are disclosed", "The least organized files may automatically receive the highest ranking"], "原来的偏差便获得了新的权威", "Repeated citation can reinforce the original selection imbalance.", "cause and effect"),
         q("What course of action does the speaker favor?", ["Publish progressively while documenting gaps and verifying additions", "Delay all access until every surviving document has been processed", "Accept all public contributions without checking their reliability", "Show only complete collections and conceal the selection criteria"], "边开放边说明缺口", "The speaker supports access with transparent limits and checked contributions.", "main idea")]),
]


def build_items():
    result, question_index = [], 0
    for skill, records in (("reading", READING), ("listening", LISTENING)):
        for index, (level, topic, genre, orientation, source, reason, qs) in enumerate(records, 1):
            item_id = f"zh_expand_{skill[0]}_{level.replace('+', 'p')}_{index:02d}"
            turns = [Turn(speaker="AB"[n % 2], text=t) for n, t in enumerate(source)] if skill == "listening" else []
            text = "\n".join(f"{t.speaker}: {t.text}" for t in turns) if turns else source
            metadata = GenerationMetadata(provider="AI-assisted original authoring", model="Codex",
                prompt_version="mandarin-range-expansion-v1",
                authoring_notes="Original simplified-Chinese fictional scenario. Provisional ILR; no empirical calibration or independent native-speaker review.")
            questions = []
            for n, (stem, answers, evidence, rationale, kind) in enumerate(qs, 1):
                offset = question_index % 4
                choices = answers[-offset:] + answers[:-offset] if offset else answers
                questions.append(QuestionItem(id=f"{item_id}_q{n}", passage_id=item_id, stem_en=stem,
                    choices=dict(zip("ABCD", choices)), correct_key="ABCD"[offset], rationale_en=rationale,
                    evidence_ru=evidence, question_type=kind, target_ilr=level,
                    provisional_difficulty=ILR_THETA[level], generation=metadata))
                question_index += 1
            passage = PassageItem(id=item_id, language="zh-CN", skill=skill, target_ilr=level,
                provisional_difficulty=ILR_THETA[level], genre=genre, topic=topic,
                subtopic=f"Original {genre}", orientation_en=orientation, passage_ru=text,
                provenance={"authoring":"Original fictional AI-assisted Mandarin practice material",
                    "difficulty_rationale":reason, "writing_system":"Simplified Chinese; no pinyin in assessment",
                    "descriptor_reference":f"https://govtilr.org/Skills/{skill.title()}.htm"},
                word_count=target_unit_count(text, "zh-CN"), question_ids=[x.id for x in questions],
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
    write_package(ROOT / "data/pilots/mandarin_range_expansion.json", ContentPackage(items=items))
    chars = sum(len(t.text) for i in items for t in i.turns)
    print(f"Built {len(items)} original drafts; {sum(len(i.questions) for i in items)} questions; {chars} listening input characters. No provider called.")
