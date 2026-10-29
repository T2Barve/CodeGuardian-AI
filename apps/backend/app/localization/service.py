"""CodeGuardian AI — Multilingual Technical Localization Service.

Provides natural, technically accurate error and vulnerability explanations
in English, Hindi (हिंदी), Hinglish, Urdu (اردو), Marathi (मराठी), and Gujarati (ગુજરાતી).
"""

from typing import Any, Dict, List, Optional
from app.schemas.localization import FindingExplanationResponse, SupportedLanguage


class MultilingualExplanationService:
    """Translates DevSecOps findings and optimization advice into regional languages."""

    LANGUAGE_METADATA = {
        SupportedLanguage.ENGLISH: {"display_name": "English (US)", "bcp47": "en-US"},
        SupportedLanguage.HINDI: {"display_name": "Hindi (हिंदी)", "bcp47": "hi-IN"},
        SupportedLanguage.HINGLISH: {"display_name": "Hinglish (Tech Conversational)", "bcp47": "hi-IN"},
        SupportedLanguage.URDU: {"display_name": "Urdu (اردو)", "bcp47": "ur-PK"},
        SupportedLanguage.MARATHI: {"display_name": "Marathi (मराठी)", "bcp47": "mr-IN"},
        SupportedLanguage.GUJARATI: {"display_name": "Gujarati (ગુજરાતી)", "bcp47": "gu-IN"},
    }

    # Technical knowledgebase for common vulnerability patterns across 6 languages
    TRANSLATION_MAP: Dict[str, Dict[SupportedLanguage, Dict[str, Any]]] = {
        "SQL_INJECTION": {
            SupportedLanguage.ENGLISH: {
                "title": "Critical SQL Injection Vulnerability",
                "summary": "Untrusted user inputs are directly concatenated into a raw database SQL query without parameterization.",
                "root_cause": "The code constructs queries using string formatting or f-strings (e.g. f'SELECT * FROM users WHERE id={user_input}'), allowing attackers to manipulate the SQL syntax.",
                "risk_impact": "Malicious actors can bypass authentication, read confidential tables, modify financial records, or drop entire databases.",
                "remediation_steps": [
                    "Use parameterized prepared statements with bind variables.",
                    "Use an ORM such as SQLAlchemy with parameterized filter expressions.",
                    "Validate and sanitize all incoming request parameters against strict schemas."
                ],
                "voice_script": "Attention developer. A critical SQL injection vulnerability was detected. User input is concatenated directly into a database query. To fix this immediately, replace string formatting with parameterized queries or SQLAlchemy bind variables."
            },
            SupportedLanguage.HINDI: {
                "title": "गंभीर SQL इंजेक्शन सुरक्षा भेदता (SQL Injection)",
                "summary": "उपयोगकर्ता से प्राप्त इनपुट को बिना किसी जांच के सीधे डेटाबेस SQL क्वेरी में जोड़ा जा रहा है।",
                "root_cause": "कोड में f-strings या स्ट्रिंग जोड़कर क्वेरी बनाई जा रही है। इससे हमलावर मनमाना SQL कोड निष्पादित कर सकते हैं।",
                "risk_impact": "हमलावर प्रमाणीकरण को दरकिनार कर सकते हैं, गोपनीय डेटा चुरा सकते हैं या पूरा डेटाबेस हटा सकते हैं।",
                "remediation_steps": [
                    "स्ट्रिंग फॉर्मेटिंग के बजाय हमेशा पैरामीटराइज़्ड क्वेरीज़ (Parameterized Queries) का उपयोग करें।",
                    "SQLAlchemy जैसे ORM के सुरक्षित फ़िल्टर मेथड्स का प्रयोग करें।",
                    "यूज़र इनपुट को कड़े Pydantic स्कीमा से सत्यापित करें।"
                ],
                "voice_script": "ध्यान दें डेवलपर। आपके कोड में एक गंभीर एसक्यूएल इंजेक्शन सुरक्षा भेदता पाई गई है। यूज़र इनपुट को सीधे डेटाबेस क्वेरी में जोड़ा गया है। कृपया स्ट्रिंग जोड़ने के बजाय पैरामीटराइज़्ड क्वेरीज़ का उपयोग करें।"
            },
            SupportedLanguage.HINGLISH: {
                "title": "Critical SQL Injection Risk",
                "summary": "User input ko direct SQL query mein concatenate kiya ja raha hai bina parameterization ke.",
                "root_cause": "Code mein f-strings ya '+' operator se query banayi gayi hai. Isse koi bhi attacker query structure ko hijack kar sakta hai.",
                "risk_impact": "Attacker database ka sara sensitive data chura sakta hai, authentication bypass kar sakta hai aur tables drop kar sakta hai.",
                "remediation_steps": [
                    "String formatting hata kar prepared statements aur parameterized queries use karein.",
                    "SQLAlchemy ORM ke safe filter methods use karein.",
                    "Har input ko strict Pydantic model se validate karein."
                ],
                "voice_script": "Hello developer! Aapke code mein SQL injection ka serious issue mila hai. User input direct query mein jud raha hai. Isko turant fix karne ke liye parameterized queries ya SQLAlchemy ORM use karein."
            },
            SupportedLanguage.URDU: {
                "title": "خطرناک ایس کیو ایل انجیکشن خامی (SQL Injection)",
                "summary": "صارف کے فراہم کردہ ڈیٹا کو بغیر جانچ پڑتال کے براہ راست ڈیٹا بیس کوئری میں شامل کیا جا رہا ہے۔",
                "root_cause": "کوڈ میں اسٹرنگ فارمیٹنگ کا استعمال کر کے کوئری تیار کی گئی ہے، جس کی وجہ سے حملہ آور کوئری کے ڈھانچے کو تبدیل کر سکتا ہے۔",
                "risk_impact": "حملہ آور حساس ڈیٹا چرا سکتا ہے، سیکیورٹی بائی پاس کر سکتا ہے، یا مکمل ڈیٹا بیس کو حذف کر سکتا ہے۔",
                "remediation_steps": [
                    "اسٹرنگ کنکیٹینیشن کے بجائے پیرامیٹرائزڈ کوئریز (Parameterized Queries) استعمال کریں۔",
                    "محفوظ ORM لائبریری جیسے SQLAlchemy کا استعمال کریں۔",
                    "تمام یوزر ان پٹس کو سخت اصولوں کے مطابق چیک کریں۔"
                ],
                "voice_script": "توجہ فرمائیں۔ آپ کے کوڈ میں ایس کیو ایل انجیکشن کی سنگین سیکیورٹی خامی موجود ہے۔ برائے مہربانی اسٹرنگ فارمیٹنگ ختم کر کے پیرامیٹرائزڈ کوئریز کا استعمال کریں۔"
            },
            SupportedLanguage.MARATHI: {
                "title": "गंभीर एसक्यूएल इंजेक्शन सुरक्षा त्रुटी (SQL Injection)",
                "summary": "वापरकर्त्याचा इनपुट कोणत्याही तपासणीविना थेट डेटाबेस एसक्यूएल क्वेरीमध्ये जोडला जात आहे.",
                "root_cause": "कोडमध्ये f-strings किंवा स्ट्रिंग कॉनकॅटिनेशन वापरले आहे, ज्यामुळे सायबर हल्लेखोर स्वतःचे एसक्यूएल कोड चालवू शकतात.",
                "risk_impact": "हल्लेखोर लॉगिन बायपास करू शकतात, संवेदनशील माहिती चोरू शकतात किंवा संपूर्ण डेटाबेस नष्ट करू शकतात.",
                "remediation_steps": [
                    "नेहमी पॅरामीटराइझ्ड क्वेरीज (Parameterized Queries) चा वापर करा.",
                    "SQLAlchemy सारख्या ओआरएम मधील सुरक्षित फिल्टर्स वापरा.",
                    "वापरकर्त्याच्या प्रत्येक इनपुटची योग्य पडताळणी करा."
                ],
                "voice_script": "लक्ष द्या. तुमच्या कोडमध्ये गंभीर एसक्यूएल इंजेक्शन त्रुटी आढळली आहे. स्ट्रिंग जोडण्याऐवजी पॅरामीटराइझ्ड क्वेरीजचा वापर करून हा धोका टाळा."
            },
            SupportedLanguage.GUJARATI: {
                "title": "ગંભીર એસક્યુએલ ઈન્જેક્શન ખામી (SQL Injection)",
                "summary": "વપરાશકર્તા પાસેથી આવતો ઇનપુટ સીધો જ ડેટાબેઝ એસક્યુએલ ક્વેરીમાં ઉમેરવામાં આવી રહ્યો છે.",
                "root_cause": "કોડમાં f-strings અથવા સ્ટ્રિંગ જોડીને ક્વેરી બનાવવામાં આવી છે, જેનાથી હેકર્સ ખોટો કોડ એક્ઝિક્યુટ કરી શકે છે.",
                "risk_impact": "હેકર્સ ગુપ્ત માહિતી ચોરી શકે છે, લોગિન સુરક્ષા તોડી શકે છે અથવા ડેટાબેઝ ઉડાવી શકે છે.",
                "remediation_steps": [
                    "સ્ટ્રિંગ જોડવાને બદલે પેરામીટરાઇઝ્ડ ક્વેરીઝ (Parameterized Queries) નો ઉપયોગ કરો.",
                    "SQLAlchemy જેવા સુરક્ષિત ORM નો ઉપયોગ કરો.",
                    "તમામ ઇનપુટ્સનું ચોક્કસ વેલિડેશન કરો."
                ],
                "voice_script": "ધ્યાન આપો. તમારા કોડમાં એસક્યુએલ ઈન્જેક્શનની ગંભીર ખામી મળી છે. સ્ટ્રિંગ જોડવાને બદલે પેરામીટરાઇઝ્ડ ક્વેરીઝનો ઉપયોગ કરીને આ સમસ્યા ઉકેલો."
            },
        },
        "HARDCODED_SECRET": {
            SupportedLanguage.ENGLISH: {
                "title": "Hardcoded Secret / API Token Exposure",
                "summary": "A plaintext credential, cryptographic key, or private token was detected in source code.",
                "root_cause": "API keys or passwords were committed directly to code files rather than loaded from environment variables.",
                "risk_impact": "Anyone with repository access can extract the credential, gain unauthorized access to cloud resources, and compromise infrastructure.",
                "remediation_steps": [
                    "Revoke and rotate the exposed credential immediately.",
                    "Store secrets exclusively in environment variables or cloud secret managers.",
                    "Add sensitive configuration files to .gitignore."
                ],
                "voice_script": "Security alert. A plaintext secret or API token was discovered in your code. Rotate the key immediately and load credentials securely from environment variables."
            },
            SupportedLanguage.HINDI: {
                "title": "हार्डकोडेड सीक्रेट या API टोकन एक्सपोज़र",
                "summary": "सोर्स कोड में प्लेनटेक्स्ट क्रेडेंशियल, गुप्त कुंजी या API टोकन पाया गया है।",
                "root_cause": "पर्यावरण चर (Environment Variables) के बजाय क्रेडेंशियल को सीधे कोड में लिख दिया गया है।",
                "risk_impact": "रिपॉजिटरी देखने वाला कोई भी व्यक्ति इस टोकन का उपयोग करके आपके क्लाउड इंफ्रास्ट्रक्चर में अनाधिकृत प्रवेश कर सकता है।",
                "remediation_steps": [
                    "इस क्रेडेंशियल को तुरंत रिवोक (Revoke) और रोटेट करें।",
                    "सीक्रेट्स को हमेशा .env या क्लाउड सीक्रेट मैनेजर में सुरक्षित रखें।",
                    "संवेदनशील फाइलों को .gitignore में जोड़ें।"
                ],
                "voice_script": "सुरक्षा चेतावनी। आपके कोड में एक हार्डकोडेड API टोकन या सीक्रेट पाया गया है। इसे तुरंत निरस्त करें और पर्यावरण चर यानी एनवायरनमेंट वेरिएबल्स का उपयोग करें।"
            },
            SupportedLanguage.HINGLISH: {
                "title": "Hardcoded Secret & API Key Leaked",
                "summary": "Code mein plaintext API key ya secret password hardcode kiya gaya hai.",
                "root_cause": "Environment variable use karne ke badle directly file ke andar credential likh diya gaya hai.",
                "risk_impact": "Koi bhi unauthorized user ya hacker is key ko use karke cloud services ko exploit kar sakta hai.",
                "remediation_steps": [
                    "Is exposed key ko turant revoke aur rotate karein.",
                    "Credentials ko .env file ya secret manager mein shift karein.",
                    "Secrets ko code repo mein commit na karein."
                ],
                "voice_script": "Developer dhyan dein. Aapke code mein API key hardcoded mili hai. Is key ko turant revoke karein aur environment variables mein move karein."
            },
            SupportedLanguage.URDU: {
                "title": "ہارڈ کوڈڈ خفیہ ٹوکن یا چابی کا انکشاف",
                "summary": "کوڈ کے اندر پاس ورڈ یا خفیہ API ٹوکن براہ راست پایا گیا ہے۔",
                "root_cause": "ماحولیاتی متغیرات (Environment Variables) استعمال کرنے کے بجائے پاس ورڈ فائل میں لکھا گیا ہے۔",
                "risk_impact": "کوئی بھی غیر مجاز شخص اس کلید کا استعمال کر کے آپ کے سرور اور کلاؤڈ سسٹم پر قبضہ کر سکتا ہے۔",
                "remediation_steps": [
                    "اس کلید کو فوراً منسوخ کر کے تبدیل کریں۔",
                    "تمام خفیہ معلومات کو .env میں محفوظ کریں۔",
                    "خفیہ فائلوں کو گٹ ریپو سے دور رکھیں۔"
                ],
                "voice_script": "سیکیورٹی الرٹ۔ آپ کے کوڈ میں خفیہ پاس ورڈ یا ٹوکن پایا گیا ہے۔ براہ کرم اس کلید کو فوراً تبدیل کریں اور محفوظ ماحولیاتی متغیرات استعمال کریں۔"
            },
            SupportedLanguage.MARATHI: {
                "title": "हार्डकोडेड पासवर्ड किंवा एपीआय की उघड झाली आहे",
                "summary": "सोर्स कोडमध्ये पासवर्ड किंवा खाजगी एपीआय टोकन उघड्या स्वरूपात सापडले आहे.",
                "root_cause": "एनव्हायर्नमेंट व्हेरिएबल्सचा वापर न करता कोड फाईलमध्ये थेट सिक्रेट्स लिहिण्यात आले आहेत.",
                "risk_impact": "कोणीही अनाधिकृत व्यक्ती या की चा वापर करून आपल्या सर्व्हरवर गैरवापर करू शकते.",
                "remediation_steps": [
                    "ही एक्सपोज झालेली की त्वरित बदला (Rotate करा).",
                    "सर्व पासवर्ड्स .env फाईलमध्ये सुरक्षित ठेवा.",
                    "सिक्रेट्स कधीही गिटवर कमिट करू नका."
                ],
                "voice_script": "सुरक्षा इशारा. तुमच्या कोडमध्ये हार्डकोडेड पासवर्ड सापडला आहे. तो त्वरित रद्द करा आणि सुरक्षित व्हेरिएबल्स वापरा."
            },
            SupportedLanguage.GUJARATI: {
                "title": "હાર્ડકોડેડ સિક્રેટ અથવા API કી બહાર આવી ગઈ છે",
                "summary": "સોર્સ કોડમાં પાસવર્ડ અથવા પ્રાઇવેટ API કી સાદા ટેક્સ્ટમાં જોવા મળી છે.",
                "root_cause": "એન્વાયરમેન્ટ વેરિયેબલ્સ વાપરવાને બદલે સીધો જ પાસવર્ડ ફાઇલમાં લખી દીધો છે.",
                "risk_impact": "કોઈપણ અનધિકૃત વ્યક્તિ આ કી વાપરીને તમારા ક્લાઉડ સિસ્ટમમાં ઘૂસણખોરી કરી શકે છે.",
                "remediation_steps": [
                    "આ કીને તાત્કાલિક રદ કરીને નવી કી બનાવો.",
                    "બધા સિક્રેટ્સને .env ફાઇલમાં સાચવો.",
                    "કોડમાં ક્યારેય પાસવર્ડ કમિટ ન કરો."
                ],
                "voice_script": "સુરક્ષા ચેતવણી. તમારા કોડમાં API કી હાર્ડકોડેડ મળી આવી છે. તેને તાત્કાલિક રદ કરો અને સુરક્ષિત રીતે સ્ટોર કરો."
            },
        },
        "PERFORMANCE_BOTTLENECK": {
            SupportedLanguage.ENGLISH: {
                "title": "Algorithmic Inefficiency: Nested Iteration O(N^2)",
                "summary": "Nested loops over datasets cause quadratic execution time, leading to severe performance degradation under scale.",
                "root_cause": "Searching through an inner collection repeatedly inside an outer loop results in O(N*M) or O(N^2) time complexity.",
                "risk_impact": "High CPU utilization, request timeouts on large inputs, and denial of service under peak production traffic.",
                "remediation_steps": [
                    "Pre-index the inner collection into a hash set or dictionary for O(1) lookups.",
                    "Transform the nested loop into a linear pass O(N) using set intersection or hash join.",
                    "Profile memory consumption to ensure constant or linear space overhead."
                ],
                "voice_script": "Performance notice. A quadratic O(N squared) nested loop was identified. By converting the inner collection to a hash set, execution time is reduced to linear O(N), yielding up to fifty times faster execution."
            },
            SupportedLanguage.HINDI: {
                "title": "एल्गोरिथम अक्षमता: नेस्टेड लूप O(N^2) जटिलता",
                "summary": "नेस्टेड लूप के कारण कोड का निष्पादन समय $O(N^2)$ हो रहा है, जिससे बड़े डेटा पर सिस्टम बेहद धीमा हो जाएगा।",
                "root_cause": "एक लूप के अंदर दूसरे लूप में बार-बार लीनियर सर्च करने से टाइम कॉम्प्लेक्सिटी अत्यधिक बढ़ जाती है।",
                "risk_impact": "उच्च CPU खपत, बड़े डेटासेट पर रिक्वेस्ट टाइमआउट और सर्वर हैंग होने का खतरा।",
                "remediation_steps": [
                    "भीतरी डेटा को हैश सेट (Hash Set) या डिक्शनरी में बदलें ताकि लुकअप O(1) में हो सके।",
                    "नेस्टेड लूप को हटाकर लीनियर O(N) एल्गोरिथ्म का प्रयोग करें।",
                    "स्ट्रिंग जोड़ने के लिए हमेशा join() मेथड का इस्तेमाल करें।"
                ],
                "voice_script": "परफॉरमेंस सूचना। आपके कोड में नेस्टेड लूप के कारण ओ एन स्क्वायर की धीमी जटिलता पाई गई है। इसे हैश सेट में बदलकर ओ एन में अनुकूलित किया जा सकता है, जिससे कोड पचास गुना तेज़ चलेगा।"
            },
            SupportedLanguage.HINGLISH: {
                "title": "Performance Bottleneck: O(N^2) Nested Loop Detected",
                "summary": "Code mein nested loop hone ki wajah se execution time O(N^2) ho gaya hai, jo large traffic par server slow kar dega.",
                "root_cause": "Outer loop ke andar inner list ko baar-baar linear scan kiya ja raha hai.",
                "risk_impact": "High CPU utilization, latency spike aur 504 Gateway Timeout errors.",
                "remediation_steps": [
                    "Inner list ko set() ya dictionary mein convert karein for O(1) instant lookup.",
                    "Algorithm ko O(N) linear time mein refactor karein.",
                    "Loops mein string concatenation (+) avoid karein aur join() use karein."
                ],
                "voice_script": "Performance update! Aapke code mein nested loop ki wajah se time complexity O(N square) hai. Isko hash set use karke O(N) linear complexity mein optimize karein for fifty times faster speed."
            },
            SupportedLanguage.URDU: {
                "title": "الگورتھم کی سستی: نیسٹڈ لوپ O(N^2)",
                "summary": "نیسٹڈ لوپس کی وجہ سے ایگزیکیوشن کا وقت بہت زیادہ بڑھ جاتا ہے، جس سے نظام سست پڑ جاتا ہے۔",
                "root_cause": "ایک لوپ کے اندر دوسرے لوپ میں بار بار تلاش کرنے سے ٹائم کمپلیکسٹی O(N^2) ہو جاتی ہے۔",
                "risk_impact": "سی پی یو پر غیر ضروری بوجھ، بڑے ڈیٹا پر سسٹم کا رک جانا اور تاخیر۔",
                "remediation_steps": [
                    "اندرونی ڈیٹا کو ہیش سیٹ یا ڈکشنری میں تبدیل کریں تاکہ فوری تلاش ممکن ہو سکے۔",
                    "نیسٹڈ لوپس کے بجائے O(N) الگورتھم استعمال کریں۔",
                    "اسٹرنگ کنکیٹینیشن کے لیے join فنکشن استعمال کریں۔"
                ],
                "voice_script": "پرفارمنس الرٹ۔ آپ کے کوڈ میں نیسٹڈ لوپ کی وجہ سے تاخیر ہو رہی ہے۔ ہیش سیٹ استعمال کر کے اس کی رفتار پچاس گنا تیز کی جا سکتی ہے۔"
            },
            SupportedLanguage.MARATHI: {
                "title": "कार्यक्षमता समस्या: नेस्टेड लूप O(N^2) संथपणा",
                "summary": "नेस्टेड लूपमुळे कोड चालण्याचा वेळ O(N^2) होतो, ज्यामुळे मोठ्या डेटावर ॲप खूप संथ होते.",
                "root_cause": "लूपच्या आत पुन्हा पुन्हा शोध घेतल्याने अल्गोरिदमची जटिलता वाढते.",
                "risk_impact": "जास्त सीपीयू वापर, विनंती टाइमआउट आणि सिस्टीम हँग होण्याचा धोका.",
                "remediation_steps": [
                    "आतील डेटा हॅश सेट (Hash Set) मध्ये रुपांतरित करा जेणेकरून O(1) मध्ये शोध घेता येईल.",
                    "नेस्टेड लूप ऐवजी O(N) लीनियर लॉजिक वापरा.",
                    "स्ट्रिंग जोडण्यासाठी नेहमी join() पद्धत वापरा."
                ],
                "voice_script": "कार्यक्षमता सूचना. कोडमधील नेस्टेड लूपमुळे गती मंदावली आहे. हॅश सेट वापरून हा कोड पन्नास पटीने वेगवान करा."
            },
            SupportedLanguage.GUJARATI: {
                "title": "પર્ફોર્મન્સ સમસ્યા: નેસ્ટેડ લૂપ O(N^2) જટિલતા",
                "summary": "નેસ્ટેડ લૂપને કારણે કોડ રન થવામાં ખૂબ સમય લે છે અને સર્વર ધીમું પડી જાય છે.",
                "root_cause": "લૂપની અંદર વારંવાર લિસ્ટમાં શોધ કરવાથી ટાઇમ કોમ્પ્લેક્સિટી વધી જાય છે.",
                "risk_impact": "સીપીયુનો ભારે ઉપયોગ અને મોટા ડેટાસેટ્સ પર એપ્લિકેશન ક્રેશ થવાનો ભય.",
                "remediation_steps": [
                    "ડેટાને હેશ સેટ અથવા ડિક્શનરીમાં બદલો જેથી O(1) માં સર્ચ થાય.",
                    "નેસ્ટેડ લૂપ દૂર કરીને O(N) લીનિયર કોડ બનાવો.",
                    "સ્ટ્રિંગ જોડવા માટે હંમેશા join() નો ઉપયોગ કરો."
                ],
                "voice_script": "પર્ફોર્મન્સ સુધારો. તમારા કોડમાં નેસ્ટેડ લૂપ છે. હેશ સેટનો ઉપયોગ કરીને તેને O(N) માં ફેરવો અને ઝડપ પચાસ ગણી વધારો."
            },
        },
    }

    def explain_finding(
        self,
        finding_id: str,
        title: str,
        description: str,
        category: str,
        severity: str,
        language: SupportedLanguage = SupportedLanguage.ENGLISH,
    ) -> FindingExplanationResponse:
        """Generates localized explanation and audio-ready narration script."""
        # Determine archetype
        upper_text = f"{title} {description} {category}".upper()
        if "SQL" in upper_text or "INJECTION" in upper_text:
            archetype = "SQL_INJECTION"
        elif "SECRET" in upper_text or "KEY" in upper_text or "TOKEN" in upper_text or "PASSWORD" in upper_text:
            archetype = "HARDCODED_SECRET"
        else:
            archetype = "PERFORMANCE_BOTTLENECK"

        trans_entry = self.TRANSLATION_MAP.get(archetype, {}).get(
            language, self.TRANSLATION_MAP[archetype][SupportedLanguage.ENGLISH]
        )
        meta = self.LANGUAGE_METADATA.get(language, self.LANGUAGE_METADATA[SupportedLanguage.ENGLISH])

        return FindingExplanationResponse(
            finding_id=finding_id,
            language=language.value,
            language_display_name=meta["display_name"],
            title=trans_entry["title"],
            summary=trans_entry["summary"],
            root_cause=trans_entry["root_cause"],
            risk_impact=trans_entry["risk_impact"],
            remediation_steps=trans_entry["remediation_steps"],
            code_example_fix=None,
            voice_script=trans_entry["voice_script"],
            audio_stream_url=f"/api/v1/findings/{finding_id}/audio?lang={language.value}",
        )
