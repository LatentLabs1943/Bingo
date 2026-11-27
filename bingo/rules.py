RULES_EN = """🃏 Cards
Choose up to 2 cards from the room's displayed range before registration closes. A room with a 20-card limit offers cartelas 1–20; the maximum is 600. Red cards belong to another player. Tap a number to preview the card, then reserve it. Each card costs the displayed demo entry fee, deducted when you reserve. You need enough available credits for each card. You can release a card during registration for a full refund. Your selected cards enter the game automatically when the countdown reaches zero.

🎮 Playing
Registration waits until the displayed minimum number of distinct players has reserved cards. If participation drops below that minimum, the countdown stops. Each player can choose at most two cards, within the room's displayed card limit.

The server calls random numbers without repetition from the displayed pool: either all numbers 1–75, or only numbers on the reserved cards. Selected-card mode changes the odds compared with the full pool. The mode, price, limits and timing are fixed once cards are reserved; admin changes apply to a later round. Automatic marking is on by default for new players. Switch it off to mark called numbers on your own cards manually; your choice is saved. The center is a free, permanently marked space.

🏆 Winning
Complete any horizontal row, vertical column, either diagonal, or all four corners. Winners are checked together at the end of each call interval, before the next number is called. Manual players must mark their numbers before that check. New rounds use a 20% house fee on every player's total entry contribution; the remaining 80% forms the prize pool. For example, 100 entry credits gives an 80-credit prize pool and a 20-credit house fee. The fee is displayed before joining and fixed for the round. The prize pool is divided equally per winning player, even if someone has two winning cards. Shares are stored exactly; the screen rounds the display to 2 decimals.

Released entries, owner-cancelled rounds, and rounds with no marked winner receive full entry refunds without a house fee. Already-reserved rounds keep their original fee terms. Empty lobbies remain open. Results stay visible briefly before the next registration opens.

This version uses demo credits only. Credits have no cash value; there are no deposits or withdrawals."""

RULES_AM = """🃏 መጫወቻ ካርድ
በክፍሉ ከሚታዩት ካርዶች እስከ 2 ካርዶች መምረጥ ይችላሉ። የክፍሉ ገደብ 20 ከሆነ ካርቴላዎች ከ1–20 ይታያሉ፤ ከፍተኛው 600 ነው። ለእያንዳንዱ ካርድ በቂ ክሬዲት ያስፈልጋል፤ ሲመርጡ ከሂሳብዎ ይቀነሳል። በቀይ የሚታዩት ካርዶች በሌላ ተጫዋች ተመርጠዋል። ካርዱን በመንካት ቁጥሮቹን ይመልከቱ፣ ከዚያም ይምረጡት። የምዝገባ ጊዜ ሲያልቅ የመረጧቸው ካርዶች በቀጥታ ወደ ጨዋታው ይገባሉ።

🎮 ጨዋታው
የምዝገባ ቆጠራው የሚጀምረው የሚያስፈልጉት የተለያዩ ተጫዋቾች ካርድ ሲመርጡ ነው። ከዝቅተኛው ብዛት በታች ከሆኑ ቆጠራው ይቆማል። አንድ ተጫዋች እስከ ሁለት ካርዶች ይመርጣል።

ሲስተሙ ከ1–75 ሁሉንም ቁጥሮች ወይም በተመረጡ ካርዶች ላይ ያሉትን ብቻ በዘፈቀደ ይጠራል። የተመረጡ ካርዶች ሁነታ ከሙሉው ቁጥር ጨዋታ የተለየ ዕድል አለው። ሁነታው በገጹ ይታያል። ካርድ ከተመረጠ በኋላ የዙሩ ህጎች አይቀየሩም። ቁጥሮች አይደገሙም። Automatic ለአዲስ ተጫዋች በነባሪ ይበራል። በእጅ ለመጫወት ያጥፉት እና የተጠሩ ቁጥሮችን ይንኩ፤ ምርጫዎ ይቀመጣል። መሃል ያለው ቦታ ነፃ እና ሁልጊዜ የተጠቆረ ነው።

🏆 አሸናፊ
ወደጎን፣ ወደታች፣ በአንዱ አግዳሚ መስመር ወይም በአራቱ ማእዘናት የተጠቆሩ ቁጥሮች ሲሞሉ ያሸንፋሉ። ቀጣዩ ቁጥር ከመጠራቱ በፊት አሸናፊዎች በአንድ ጊዜ ይረጋገጣሉ። በእጅ የሚጫወቱ ተጫዋቾች ከዚያ በፊት ቁጥሮቻቸውን ማጥቆር አለባቸው። አዳዲስ ዙሮች ከእያንዳንዱ ተጫዋች ጠቅላላ መግቢያ 20% ለአዘጋጁ ይቀንሳሉ፤ የቀረው 80% ሽልማት ይሆናል። ለምሳሌ 100 ክሬዲት መግቢያ 80 ክሬዲት ሽልማት እና 20 ክሬዲት የአዘጋጅ ክፍያ ይሆናል። ክፍያው ከመምረጥዎ በፊት ይታያል እና በዙሩ አይቀየርም። እኩል ያሸነፉ ተጫዋቾች የቀረውን ሽልማት በእኩል ይካፈላሉ። የተለቀቁ ካርዶች፣ የተሰረዙ ዙሮች እና አሸናፊ የሌላቸው ዙሮች ሙሉ መግቢያ ይመልሳሉ፤ የአዘጋጅ ክፍያ አይቀነስም።

ይህ የሙከራ ጨዋታ ነው። ክሬዲቶቹ የገንዘብ ዋጋ የላቸውም።"""


def rules_for(settings, language):
    text = RULES_AM if language == "am" else RULES_EN
    if settings.funds_mode == "manual":
        if language == "am":
            text = text.replace("ይህ የሙከራ ጨዋታ ነው። ክሬዲቶቹ የገንዘብ ዋጋ የላቸውም።",
                "1 ክሬዲት = 1 ብር። ገቢ ከአስተዳዳሪ ማረጋገጫ በኋላ ይጨመራል። የወጪ ጥያቄ ክሬዲቶቹን ይይዛል፤ ከተከለከለ ይመለሳሉ። ዝውውሩ በእጅ ወደ ተረጋገጠው ሂሳብዎ ይከናወናል። የሙከራ ክሬዲት ወደ ብር አይቀየርም።")
        else:
            text = text.replace("demo entry fee", "credit entry fee").replace(
                "This version uses demo credits only. Credits have no cash value; there are no deposits or withdrawals.",
                "1 credit = 1 birr. Deposits require an admin to verify the actual transfer before adding credits. Withdrawals reserve credits pending a manual transfer to the verified account; rejection returns the held credits. Practice balances are separate and cannot be withdrawn.")
    return text

