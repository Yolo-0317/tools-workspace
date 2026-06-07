#!/usr/bin/env python3
"""Regenerate lessons.json v5 from 沪教牛津版(六三制) textbook unit TOCs.

Usage:
    cd english-buddy/backend && python3 teaching/build_lessons_v5.py

See docs/CURRICULUM.md for structure and version bump behavior.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent / "lessons.json"

KG = {
    "kg_small": [
        ("kgs_hello", "第1课 · Hello", 1, "Hello!\nHi!\nGood morning!\nBye bye!\nSee you!"),
        ("kgs_colors", "第2课 · Colors", 2, "Red!\nBlue!\nYellow!\nGreen!\nI like red."),
        ("kgs_numbers", "第3课 · Numbers", 3, "One.\nTwo.\nThree.\nFour.\nFive."),
        ("kgs_animals", "第4课 · Animals", 4, "A cat.\nA dog.\nA bird.\nA fish.\nI like cats."),
        ("kgs_body", "第5课 · My body", 5, "My eyes.\nMy nose.\nMy mouth.\nMy ears.\nTouch your nose."),
        ("kgs_family", "第6课 · Family", 6, "Mum.\nDad.\nI love Mum.\nI love Dad.\nMy family."),
    ],
    "kg_middle": [
        ("kgm_hello", "第1课 · Hello, friend", 1, "Hello, my friend!\nHow are you?\nI am fine.\nThank you!\nNice to meet you!"),
        ("kgm_colors", "第2课 · Colors and shapes", 2, "What color is it?\nIt is red.\nIt is a circle.\nIt is a square.\nI see blue."),
        ("kgm_numbers", "第3课 · Count with me", 3, "Let's count.\nOne, two, three.\nFour little ducks.\nFive little stars.\nHow many?"),
        ("kgm_animals", "第4课 · Animals", 4, "Look at the cat.\nThe dog can run.\nThe bird can fly.\nI like pandas.\nAnimals are fun."),
        ("kgm_family", "第5课 · My family", 5, "This is my mum.\nThis is my dad.\nShe is kind.\nHe is tall.\nI love my family."),
        ("kgm_fruit", "第6课 · I like bananas", 6, "An apple, please.\nI like bananas.\nI like grapes, too.\nYummy fruit!\nThank you!"),
        ("kgm_weather", "第7课 · Sunny day", 7, "It is sunny.\nIt is rainy.\nPut on your coat.\nLet's go outside.\nWhat a nice day!"),
    ],
    "kg_large": [
        ("kgl_morning", "第1课 · Good morning", 1, "Good morning, teacher!\nGood morning, class!\nHow are you today?\nI am very happy.\nLet's start!"),
        ("kgl_classroom", "第2课 · In the classroom", 2, "This is our classroom.\nSit down, please.\nOpen your book.\nListen to me.\nRaise your hand."),
        ("kgl_can", "第3课 · I can", 3, "I can sing.\nI can dance.\nI can draw.\nCan you swim?\nYes, I can!"),
        ("kgl_park", "第4课 · At the park", 4, "Let's go to the park.\nRun on the grass.\nFly a kite.\nPlay on the slide.\nHave fun!"),
        ("kgl_weather", "第5课 · Weather", 5, "How is the weather?\nIt is warm today.\nIt is windy.\nTake your umbrella.\nI like sunny days."),
        ("kgl_school", "第6课 · Ready for school", 6, "I go to school.\nMy bag is blue.\nI meet my friends.\nWe learn English.\nSchool is great!"),
        ("kgl_thanks", "第7课 · Thank you", 7, "Thank you very much.\nYou are welcome.\nPlease and sorry.\nBe polite.\nGood manners!"),
        ("kgl_review", "第8课 · Review", 8, "Hello, I am Lily.\nI am six years old.\nI like English class.\nI can read and sing.\nSee you tomorrow!"),
    ],
}

# 牛津阅读树：Biff / Chip / Kipper + Mum / Dad / Floppy；原创短句（非教材原文）
ORT = {
    "ort_dialogue": [
        (
            "ort_morning",
            "第1课 · Good morning",
            1,
            "Good morning, Mum!\nGood morning, Kipper.\nAre you hungry, Chip?\nYes, I am hungry.\nBreakfast is ready!",
        ),
        (
            "ort_dog",
            "第2课 · Where is Floppy?",
            2,
            "Where is Floppy?\nIs he in the garden?\nNo, he is not there.\nLook! Floppy is on the bed.\nSilly Floppy!",
        ),
        (
            "ort_park",
            "第3课 · At the park",
            3,
            "Let's go to the park.\nCan you see the swings?\nPush me, Biff!\nPush me, Chip!\nThis is fun, Kipper!",
        ),
        (
            "ort_rain",
            "第4课 · Oh no, rain",
            4,
            "Look at the rain.\nOh no! It is wet.\nTake your coat, Kipper.\nWe can play inside.\nThat is OK, Mum.",
        ),
        (
            "ort_shop",
            "第5课 · At the shop",
            5,
            "We go to the shop.\nCan I have an apple?\nYes, you can, Kipper.\nHere you are.\nThank you, Mum.",
        ),
        (
            "ort_key",
            "第6课 · The little key",
            6,
            "What is this, Chip?\nIt is a little key.\nThe door is open.\nLook inside, Biff!\nWhat can you see?",
        ),
        (
            "ort_toy",
            "第7课 · Lost toy",
            7,
            "I cannot find my toy.\nHelp me, Biff!\nIs it under the chair?\nLook on the bed, Kipper.\nHere it is!",
        ),
        (
            "ort_bedtime",
            "第8课 · Bedtime",
            8,
            "It is bedtime, Kipper.\nBrush your teeth, please.\nRead a story, Chip.\nGood night, Mum.\nGood night, Dad!",
        ),
        (
            "ort_school",
            "第9课 · At school",
            9,
            "This is my school.\nHello, I am Kipper.\nBiff is my big sister.\nChip is my brother.\nSchool is fun!",
        ),
        (
            "ort_picnic",
            "第10课 · Picnic day",
            10,
            "It is sunny today.\nPack a picnic, Mum.\nSit on the mat.\nPass the juice, Chip.\nWhat a lovely day!",
        ),
        (
            "ort_mud",
            "第11课 · Muddy shoes",
            11,
            "Look at Floppy!\nOh no! He is muddy.\nLook at your shoes, Kipper!\nTake them off, please.\nAll clean now!",
        ),
        (
            "ort_help",
            "第12课 · Can you help?",
            12,
            "Can you help me, Chip?\nYes, I can help.\nHold the bag, Biff.\nThank you very much.\nYou are kind!",
        ),
    ],
}

# (grade_id, title, subtitle, semester, book, units[(num, en_title, lines)])
PRIMARY = [
    (
        "g1_up",
        "一年级",
        "上册",
        "上",
        "Module 1–4 · 12 单元",
        [
            (1, "Hello", "Hello!\nHi, I am Sam.\nGood morning, Miss Li.\nGoodbye, see you!\nNice to meet you!"),
            (2, "My classmates", "This is my class.\nHe is my friend.\nShe is my classmate.\nWe are in Class One.\nWe say hello together."),
            (3, "My face", "This is my face.\nI have two eyes.\nTouch your nose.\nMy mouth is small.\nSmile, please!"),
            (4, "I can sing", "I can sing a song.\nI can dance, too.\nCan you draw?\nYes, I can draw.\nWe like music."),
            (5, "My family", "This is my family.\nThis is my father.\nThis is my mother.\nI love my family.\nWe are happy together."),
            (6, "My friends", "This is my friend.\nWe play together.\nShe is very kind.\nHe is funny.\nFriends are great!"),
            (7, "Let's count", "Let's count together.\nOne, two, three.\nHow many books?\nFour books on the desk.\nFive pencils in my bag."),
            (8, "Apples, please", "Apples, please.\nMay I have one?\nHere you are.\nThank you very much.\nI like red apples."),
            (9, "May I have a pie?", "May I have a pie?\nHere you are.\nThank you, Mum.\nIt smells good.\nYummy pie!"),
            (10, "On the farm", "We are on the farm.\nI can see a cow.\nThe duck says quack.\nThe pig is fat.\nLet's feed the animals."),
            (11, "In the zoo", "Welcome to the zoo.\nLook at the tiger.\nThe monkey can climb.\nThe panda is cute.\nI like the zoo."),
            (12, "In the park", "Let's go to the park.\nThe flowers are pretty.\nWe run on the grass.\nFly a kite, please.\nI love the park."),
        ],
    ),
    (
        "g1_down",
        "一年级",
        "下册",
        "下",
        "Module 1–4 · 12 单元",
        [
            (1, "Look and see", "Look and see.\nWhat can you see?\nI can see a bird.\nIt is yellow.\nLook at the sky."),
            (2, "Listen and hear", "Listen and hear.\nWhat can you hear?\nI can hear a dog.\nI can hear a bell.\nBe quiet, please."),
            (3, "Taste and smell", "Taste and smell.\nIt is sweet.\nIt smells nice.\nI like the cake.\nYummy food!"),
            (4, "Toys I like", "I like my doll.\nI like toy cars.\nThis ball is red.\nLet's play together.\nToys are fun."),
            (5, "Food I like", "I like noodles.\nI like rice, too.\nDo you like fish?\nYes, I like fish.\nFood is yummy."),
            (6, "Drinks I like", "I like milk.\nI like juice, too.\nWater is good.\nMay I have tea?\nThank you, Mum."),
            (7, "Seasons", "Spring is warm.\nSummer is hot.\nAutumn is cool.\nWinter is cold.\nI like spring."),
            (8, "Weather", "How is the weather?\nIt is sunny today.\nIt is rainy now.\nTake your umbrella.\nLet's go home."),
            (9, "Clothes", "Put on your coat.\nMy shirt is blue.\nThese shoes are new.\nI like this dress.\nI am ready."),
            (10, "Activities", "I can run fast.\nI can jump high.\nLet's ride a bike.\nWe play ball games.\nActivities are fun."),
            (11, "New Year's Day", "Happy New Year!\nWe sing a song.\nWe visit family.\nI get a gift.\nWhat a happy day!"),
            (12, "A boy and a wolf", "A boy and a wolf.\nListen to me.\nTell the truth.\nDo not lie.\nBe a good child."),
        ],
    ),
    (
        "g2_up",
        "二年级",
        "上册",
        "上",
        "Module 1–4 · 12 单元",
        [
            (1, "Good morning", "Good morning, class!\nGood morning, teacher!\nHow are you today?\nI am fine, thank you.\nLet's begin."),
            (2, "I'm Danny", "Are you Alice?\nNo, I am Danny.\nI am eight years old.\nMy name is Danny.\nNice to meet you!"),
            (3, "Are you Alice?", "Are you Alice?\nYes, I am Alice.\nAre you a new pupil?\nYes, I am new here.\nWelcome to our class!"),
            (4, "Can you swim?", "Can you swim?\nYes, I can swim.\nCan you run fast?\nNo, I cannot run.\nI can draw and sing."),
            (5, "That's my family", "This is my mother.\nShe is a nurse.\nThat is my father.\nHe is a teacher.\nI love my family."),
            (6, "My hair is short", "My hair is short.\nYour hair is long.\nHe is tall and thin.\nShe is my classmate.\nWe are good friends."),
            (7, "In the playground", "Let's play in the park.\nGo to the slide.\nWave your hand!\nRun on the grass.\nHave fun, everyone!"),
            (8, "In my room", "Where is my book?\nIt is on the desk.\nIs it under the bed?\nNo, it is in the bag.\nPut it on the desk."),
            (9, "Dinner is ready", "Dinner is ready.\nMay I have some noodles?\nHave some milk, please.\nDo you like hot dogs?\nYes, I like hot dogs."),
            (10, "In the sky", "What can you see in the sky?\nI can see the moon.\nLook at the big stars.\nI can see a cloud.\nThe sky is blue."),
            (11, "In the forest", "We walk in the forest.\nI can see a bear.\nThe trees are tall.\nBirds sing in trees.\nNature is beautiful."),
            (12, "In the street", "We walk in the street.\nStop at the light.\nLook left and right.\nThe shop is near.\nBe careful, please."),
        ],
    ),
    (
        "g2_down",
        "二年级",
        "下册",
        "下",
        "Module 1–4 · 12 单元",
        [
            (1, "What can you see?", "What can you see?\nI can see a bear.\nWhat colour is it?\nIt is brown.\nLook at the picture."),
            (2, "Touch and feel", "Touch and feel.\nIt is soft.\nIt is hard.\nIs it smooth?\nFeel the bag."),
            (3, "What can you hear?", "What can you hear?\nI can hear a train.\nI can hear a bell.\nListen carefully.\nBe quiet, please."),
            (4, "Things I like doing", "I like reading books.\nI like riding bikes.\nWhat do you like doing?\nI like drawing pictures.\nIt is fun."),
            (5, "My favourite food", "My favourite food is noodles.\nI like rice, too.\nDo you like vegetables?\nYes, they are healthy.\nLet's eat together."),
            (6, "Animals I like", "I like pandas best.\nI like rabbits, too.\nThe panda is cute.\nAnimals are our friends.\nI love animals."),
            (7, "The four seasons", "There are four seasons.\nSpring is warm and green.\nSummer is hot and sunny.\nWinter is cold and snowy.\nI like autumn."),
            (8, "Rules", "Follow the rules.\nLine up, please.\nDo not run inside.\nBe kind to friends.\nGood pupils listen."),
            (9, "My clothes", "Put on your jacket.\nMy T-shirt is blue.\nThese socks are warm.\nI like this hat.\nI am ready to go."),
            (10, "Activities", "We play football today.\nLet's skip rope.\nI can swim well.\nWe have PE class.\nSports are fun."),
            (11, "Mother's Day", "Happy Mother's Day!\nI love you, Mum.\nI make a card.\nThank you for everything.\nYou are the best."),
            (12, "A girl and three bears", "A girl and three bears.\nThis porridge is hot.\nThis bed is soft.\nThey come back home.\nWhat a funny story!"),
        ],
    ),
    (
        "g3_up",
        "三年级",
        "上册",
        "上",
        "2024 新教材 · 8 单元",
        [
            (1, "How do we feel?", "How do we feel today?\nI feel happy.\nShe feels tired.\nAre you sad?\nTell me, please."),
            (2, "What's interesting about families?", "Families are different.\nMy family is big.\nHer family is small.\nWe help each other.\nFamilies are special."),
            (3, "What do we look like?", "What do we look like?\nI have short hair.\nHe wears glasses.\nShe has a red bag.\nWe look different."),
            (4, "How do we have fun?", "How do we have fun?\nWe play games.\nWe fly kites.\nLet's ride bikes.\nFun with friends!"),
            (5, "What do we eat?", "What do we eat for lunch?\nWe eat rice and fish.\nFruit is healthy.\nDrink water every day.\nEat balanced meals."),
            (6, "What do we like about small animals?", "I like small rabbits.\nThe hamster is cute.\nBirds can sing songs.\nPets need our care.\nAnimals are lovely."),
            (7, "What do we know about weather?", "What is the weather like?\nIt is windy today.\nIt may rain later.\nTake your umbrella.\nCheck the forecast."),
            (8, "Why do we like birthdays?", "Why do we like birthdays?\nWe eat cake together.\nWe sing Happy Birthday.\nFriends give gifts.\nBirthdays are fun!"),
        ],
    ),
    (
        "g3_down",
        "三年级",
        "下册",
        "下",
        "2024 新教材 · 8 单元",
        [
            (1, "How do we spend our free time?", "How do we spend free time?\nI read comic books.\nWe play board games.\nLet's draw pictures.\nFree time is happy."),
            (2, "How do we make friends?", "How do we make friends?\nSay hello first.\nShare your toys.\nBe kind and polite.\nFriends help each other."),
            (3, "What do we wear?", "What do we wear today?\nI wear a T-shirt.\nPut on your shoes.\nIt is cold outside.\nDress for the weather."),
            (4, "What sounds can we hear?", "What sounds can we hear?\nI hear birds sing.\nI hear cars pass.\nListen in the park.\nSounds are everywhere."),
            (5, "Where can we see colours?", "Where can we see colours?\nRainbows have many colours.\nFlowers are bright.\nThe sky is blue.\nColours are beautiful."),
            (6, "What are our homes like?", "What are our homes like?\nMy home is cosy.\nWe have a kitchen.\nMy room is small.\nHome is warm."),
            (7, "What do we do at school?", "What do we do at school?\nWe read and write.\nWe do science labs.\nWe respect teachers.\nSchool is important."),
            (8, "What do you do on Children's Day?", "Happy Children's Day!\nWe watch a show.\nWe play fun games.\nNo homework today!\nEnjoy your holiday."),
        ],
    ),
    (
        "g4_up",
        "四年级",
        "上册",
        "上",
        "Module 1–4 · 12 单元",
        [
            (1, "Meeting new people", "I am new in this school.\nMay I sit with you?\nWhere are you from?\nI am from Shanghai.\nLet's be friends!"),
            (2, "Can you swim?", "Can you swim well?\nYes, I can swim.\nCan you play piano?\nNo, I cannot play.\nI can run fast."),
            (3, "Are you happy?", "Are you happy today?\nYes, I am happy.\nWhy are you sad?\nI lost my pen.\nCheer up, friend!"),
            (4, "Do you have any cousins?", "Do you have cousins?\nYes, I have two.\nThey live in Beijing.\nWe visit in summer.\nFamily is big."),
            (5, "My friends", "My friend is helpful.\nWe study together.\nShe tells funny jokes.\nHe shares his snacks.\nFriends are important."),
            (6, "My parents", "My father works hard.\nMy mother cooks well.\nThey love me dearly.\nI help at home.\nI love my parents."),
            (7, "At school", "Our school is large.\nWe have a library.\nArt class is fun.\nBe quiet in class.\nStudy every day."),
            (8, "At the shop", "Let's go to the shop.\nHow much is it?\nIt is too expensive.\nMay I try this on?\nThank you, shopkeeper."),
            (9, "At home", "At home I read books.\nI help wash dishes.\nMy cat sleeps a lot.\nHome feels safe.\nI love my home."),
            (10, "Around my home", "Around my home there is a park.\nA bakery is nearby.\nThe street is busy.\nI walk to school.\nMy neighbourhood is nice."),
            (11, "Shapes", "A circle is round.\nA square has four sides.\nTriangles have three corners.\nDraw a rectangle.\nShapes are everywhere."),
            (12, "Weather", "How is the weather today?\nIt is cloudy and cool.\nIt may rain later.\nTake your umbrella.\nI hope it gets sunny."),
        ],
    ),
    (
        "g4_down",
        "四年级",
        "下册",
        "下",
        "Module 1–4 · 12 单元",
        [
            (1, "Touch and feel", "Touch this teddy bear.\nIt feels soft.\nThe stone is hard.\nIs it rough or smooth?\nUse your hands."),
            (2, "Smell and taste", "Smell the flowers.\nThey smell sweet.\nTaste the lemon.\nIt is sour.\nFood tastes different."),
            (3, "Look and see", "Look and see the stars.\nI see a bright moon.\nThe lake is calm.\nBirds fly across the sky.\nNature is beautiful."),
            (4, "Subjects", "I like English class.\nMath is interesting.\nWe have science today.\nMusic makes me happy.\nStudy all subjects."),
            (5, "Sport", "Do you like playing sports?\nI enjoy basketball.\nShe runs very fast.\nLet's have a race.\nSports make us strong."),
            (6, "Music", "We sing in music class.\nListen to the drum.\nClap to the rhythm.\nI play the recorder.\nMusic is wonderful."),
            (7, "My day", "I get up at seven.\nI eat breakfast early.\nSchool starts at eight.\nI do homework at night.\nThat is my day."),
            (8, "Days of the week", "Monday is busy.\nTuesday we have art.\nFriday is my favourite.\nSunday I rest at home.\nSeven days a week."),
            (9, "A friend in Australia", "I have a friend abroad.\nShe lives in Australia.\nWe write emails.\nKangaroos live there.\nFriends far away matter."),
            (10, "My garden", "My garden has roses.\nBees visit the flowers.\nI water the plants.\nGreen leaves grow fast.\nI love my garden."),
            (11, "Children's Day", "Happy Children's Day!\nWe have a school party.\nGames and songs today.\nNo tests this morning.\nEnjoy the holiday!"),
            (12, "The ugly duckling", "The ugly duckling story.\nHe looks different.\nHe grows into a swan.\nBe kind to others.\nEveryone is special."),
        ],
    ),
    (
        "g5_up",
        "五年级",
        "上册",
        "上",
        "Module 1–4 · 12 单元",
        [
            (1, "My future", "What do you want to be?\nI want to be a teacher.\nStudy hard every day.\nDreams can come true.\nYour future is bright."),
            (2, "Going to school", "How do you go to school?\nI go by subway.\nShe walks to school.\nWe must be on time.\nSafety comes first."),
            (3, "My birthday", "When is your birthday?\nMy birthday is in May.\nWe eat cake together.\nI get lovely gifts.\nHappy birthday to you!"),
            (4, "Grandparents", "I visit my grandparents.\nGrandpa tells old stories.\nGrandma cooks soup.\nI love them dearly.\nFamily ties matter."),
            (5, "Friends", "A good friend listens.\nWe trust each other.\nNever laugh at others.\nHelp when friends need.\nFriendship is precious."),
            (6, "Family life", "We share housework.\nDad washes the dishes.\nI tidy my room.\nFamily life is busy.\nWe care for each other."),
            (7, "At the beach", "We go to the beach.\nThe sand is warm.\nI can swim in the sea.\nBuild a sandcastle.\nWhat a sunny day!"),
            (8, "An outing", "We plan an outing.\nPack food and water.\nDo not litter, please.\nTake photos together.\nOutings are exciting."),
            (9, "Around the city", "Around the city we see museums.\nThe metro is fast.\nAsk for directions.\nShanghai is busy.\nCities are interesting."),
            (10, "Wind", "Wind blows the kites.\nStrong wind moves trees.\nGentle wind feels cool.\nWind can be helpful.\nNature has power."),
            (11, "Water", "Water is important.\nWe should save water.\nTurn off the tap.\nPlants need water too.\nDo not waste water."),
            (12, "Fire", "Fire can be dangerous.\nDo not play with matches.\nCall adults for help.\nLearn fire safety rules.\nStay safe always."),
        ],
    ),
    (
        "g5_down",
        "五年级",
        "下册",
        "下",
        "Module 1–4 · 12 单元",
        [
            (1, "Tidy up!", "Tidy up your room.\nPut toys in the box.\nFold your clothes.\nA clean room feels nice.\nLet's tidy up now!"),
            (2, "Our new home", "We move to a new home.\nMy room is bigger.\nWe unpack the boxes.\nNeighbours say hello.\nWelcome to our home."),
            (3, "In the future", "In the future I will travel.\nRobots may help us.\nStudy English well.\nKeep healthy habits.\nPlan for tomorrow."),
            (4, "Reading is fun", "Reading is fun.\nBooks open new worlds.\nRead a little daily.\nLibraries are quiet.\nStories teach us much."),
            (5, "At the weekend", "At the weekend I rest.\nWe visit the museum.\nSometimes I play sports.\nHomework comes first.\nEnjoy your weekend."),
            (7, "Open day", "School open day is coming.\nParents visit our class.\nWe show our projects.\nTeachers greet families.\nWe feel proud today."),
            (8, "Buying clothes", "I am buying clothes.\nThis shirt fits me.\nMay I try size small?\nBlue looks good on me.\nThank you, assistant."),
            (9, "Seeing the doctor", "I do not feel well.\nI have a sore throat.\nThe doctor helps me.\nTake medicine on time.\nRest and drink water."),
            (10, "Great inventions", "Great inventions change life.\nThe wheel helps transport.\nPhones connect people.\nThink like an inventor.\nIdeas can improve life."),
            (11, "Chinese festivals", "Chinese festivals are special.\nSpring Festival is important.\nWe eat dumplings together.\nMid-Autumn has mooncakes.\nFestivals bring families close."),
            (12, "The giant's garden", "The giant's garden story.\nSpring comes to the garden.\nChildren play happily.\nSharing brings joy.\nKindness wins at last."),
        ],
    ),
]


def slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")
    return s[:40] or "unit"


def build() -> dict:
    grades = [
        {
            "id": "kg_small",
            "title": "小班",
            "subtitle": "3～4 岁启蒙",
            "stage": "kindergarten",
            "stage_label": "幼儿园",
            "book": "问候 · 颜色 · 动物",
        },
        {
            "id": "kg_middle",
            "title": "中班",
            "subtitle": "4～5 岁",
            "stage": "kindergarten",
            "stage_label": "幼儿园",
            "book": "数字 · 家庭 · 水果",
        },
        {
            "id": "kg_large",
            "title": "大班",
            "subtitle": "5～6 岁 · 幼小衔接",
            "stage": "kindergarten",
            "stage_label": "幼儿园",
            "book": "课堂 · 天气 · 入园准备",
        },
    ]
    lessons: dict[str, list] = {k: [] for k in KG}
    lessons.update({k: [] for k in ORT})

    for gid, items in KG.items():
        for lid, title, unit, text in items:
            lessons[gid].append(
                {"id": lid, "title": title, "unit": unit, "text": text}
            )

    grades.append(
        {
            "id": "ort_dialogue",
            "title": "牛津阅读树",
            "subtitle": "Biff · Chip · Kipper · 4～7 岁",
            "stage": "kindergarten",
            "stage_label": "拓展",
            "book": "Mum / Dad / Floppy · 原创短句跟读",
        }
    )
    for gid, items in ORT.items():
        for lid, title, unit, text in items:
            lessons[gid].append(
                {"id": lid, "title": title, "unit": unit, "text": text}
            )

    for gid, gtitle, subtitle, semester, book, units in PRIMARY:
        grades.append(
            {
                "id": gid,
                "title": gtitle,
                "subtitle": subtitle,
                "stage": "primary",
                "stage_label": "小学",
                "semester": semester,
                "book": book,
            }
        )
        lessons[gid] = []
        prefix = gid.replace("_", "")
        for num, en, text in units:
            lessons[gid].append(
                {
                    "id": f"{prefix}_u{num}",
                    "title": f"Unit {num} · {en}",
                    "unit": num,
                    "text": text,
                }
            )

    return {
        "version": 8,
        "curriculum": "上海幼儿园启蒙 + 沪教牛津小学 + 牛津阅读树对话",
        "source": "小学目录参考沪教牛津版(六三制)；牛津阅读树为 Biff/Chip/Kipper 家庭原创短句（每行≤10词），非 ORT 教材原文。",
        "note": "牛津阅读树用书里角色名 Mum/Dad/Floppy；句式原创。三年级起 8 单元/册，一二年级 12 单元/册。",
        "grades": grades,
        "lessons": lessons,
    }


def main() -> None:
    data = build()
    OUT.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    n = sum(len(v) for v in data["lessons"].values())
    print(f"wrote {OUT} grades={len(data['grades'])} lessons={n}")


if __name__ == "__main__":
    main()
