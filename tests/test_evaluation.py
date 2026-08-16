import copy
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid


PACKAGE_ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from evaluation import (  # noqa: E402
    EvaluationError,
    build_report as _build_report,
    canonical_digest,
    extract_production_facts,
    validate_campaign as _validate_campaign,
    validate_evidence_chain,
    validate_production_fact,
)
from evaluation.production_facts import _metric  # noqa: E402


DIGEST = "a" * 64
DEVELOPMENT_AUTHORITY = "d" * 64
SEALED_AUTHORITY = "e" * 64
RUBRIC_DIGEST = "175477d27e98477551afa3de27d6792b128110b4fa9a37de7a87783d4303eb0c"


TEST_AUTHORITY_SIGNATURES = {'0f0d1ef28a0a13622685571fd7debf3b4ee8b8f4c712beeb543997e6777d2ff3': '64d8e27aae579a74a268db4a435a652c14e3ca98145e2e80535df6ff1c61f3905cd68edbaa71d2fa5569cc53c3921220e07ba49725966266ca6030b87ede1453daffc700f4a6c40a761ff16f063e67ba1faac312e4befc22c1fb35674f63aa315638eef0a49ab16fbf0990eafa2f2ce50747d05bd0e0b068bc6bc0fe973a0fd73d85d26b1a2f21426872177be022c289832c1be0c9c684e49bd9116ec9156c128e9c04690485617dad1b3a7c0c1b2644f7ebc52a76847a493bb088b9486f8e43138ad942745b5c37432d73cf0ce26b642398d2e7720247ec8a7d3b06e4336c03322af0b16d6ee73d3a71854222a734fa8a5c59f5006df9a836321714e1c233e7',
 '164631bd0853873b4e2c2d590ccd3bec5d410ca7b962c63702155bc40ea6309f': '75791f454bc2459aad76d145e55ba61b6c4db200330e6c92a956c9a5b8d46fdf44b7019f3aa146bb4dbf510f28155b03e8b5ddc0c1faa65aef193169d5ceb94e3f5a1c231a45a649209a3a9aa902ee7d35e21ecbdd2bafd73c9f311a769dcd8a0f226c7ba7a4fde1eedb95de225b4534e840aad39596ac96f323c2c8a12d07882c8ec773030fc36e624a8ca9280cafd08cd0043627391a02c4484ed77922e5f05044419dd5d81438737e7bb781be6e552c937e5c4b7b9c34b438020dd9acd842333e93ec5dc373efa89c100f57ec5d971ae4222ec89e0dc5ce441958f76331e3635bdf34d1e69acebab3fa3fa315d8b7618ad589061f8e8736a33732a69aac59',
 '21ba8b389182fd1289e47636a7f5251a1fa0b16870f4d5b1e5f25141631d6812': '0c94c830e32d899e742801f37569506ed520ab0a0f75dad5c4e4a8dd4c9095b9b2234887fc2057c1a69f041b419d623df7017ef874e228154da65a109f079be8500013d35edf1e1d2f88bb61abcd35631324642d93f3062c68d7135f533f85015e7f7b08064ac5e6c4f9769bf4e2c258332a929de82024fb6f42df69247381d4f9ea232e9ccd752cc8c8d443d65203c37ce3b85941bcda484ccc7b541d14613cfa9c05f7d654f0c115b092477e1419f109483cd88c8b213de37435670bda8acfc5721bce95439ac44a106959306f835b78dcc5014e0e20f6cf9fd7a10868e0704e955bfa3a5b76321f1a6c6e0b1db5b0e35acf30c20a731abd07b2103dba9800',
 '31cd294c740d33efc06f27651f260927d3ff1cc5f5450a4bac1f1d6762c16f64': '465a12897a3d16c2e564746d52c36a06e619c49f9357cacb520e71114abd57eb63fcda0043f1d4ba2fdd7981e227a5ca94d9463c7076605335491847324376b1e2f18b760f706f0d53f61b7c0838607c778498a1657ba88e3ddaf833ede48762b022022cf9078d72f6636c918dc2a81a721008991f4605e728f219acd8974944b53dad196ff564bca9b76c04676878f6e1b2abc4ad4b5d703e52f044b8448b3c0d2bdda48dcba1809037c5c384067006ddf4d0f4e779c3b82c983621a295759e7ea22b6b2536f0a2dea85dc0427098a6f13f06ea54625439af091b681a9caedaf6c733ea131c0b948967599a4e89c4aa018fbbc67ff5f304cf225acd0ccb4e32',
 '455a4e2e3f03a73025de3b446026a13ea394aace17b86605ef319228121016c6': '4a83d832f272e7e22391d56ebdf6273937939f233a77dd05052179e59d8198bdede8d6d67bb7ce370a0659a92c5b0fe0e389398891cd9692b060b08e94ff6e59f98f67b2fda5ca740237eefed8db6fba1d833e600497bbef062c4bed01fe3fdcd5f2b1b9a16287091c5af1a6b46c0862e67585d1822386fd039b62b48d32efc802566aa8ed52b5ddef0c756ec93bd5e70acbab47a924ff5ce780877222f03c99e0b51e5bc532c8640a5cbd8924c6370299d5048620d1e81ea6c30b845504c0b01a30c7c9e540777dfcc53884128f8ed1aa9c0c0906c2acd6cd99cbdb3afbed3d6ba006526f7e1b38faad6ce8b1c8fed0c22c39fb49ae463e2feef6b240935b14',
 '5088515f53a938eea9f3e64610b746717192510c66a266defb27743459a41b12': '1c52d2258afccf8e152ae4c3a1d0ae9f1a8eecb19f5b985e0c9052010f78da02be0245ef34681d2232886aa678e894bd36e0e68b434741038a8d8b7699866bedb7d8c5e5a379140b7da49edf58ac1aef8039e2ab58f0bab8d21f9798ed3fbf6f6404b86f4990363839599863b1f4f45e654e99a66c67f366d05dc94607674f15da5bf2215058693896490a2ab30f6f200fe1480970fb006792ae367374f114934b6226b3bb7c05e8bd892e6a9d0451a8ef919adfb3a83b19ee863b1cb458d5704e06122d692bdcdf5894edb0c53f6fcaf18ff1b6d2bf6c546252d0b0aff97d6fa70187d62941d7bc044503e8681323bed3e53178114ecdea252eecd68a5543e7',
 '5aafbdc8b714cfb612723444db7c5bde3b5e9136601dfbcb4ae6cd3936c0b9e1': '4a22629d45e1f45157f66caec33cf3d3d845184ac116a8d5737aa063490995ce00b0fd25e9d7d0309055fd44a10ddbabd5b7c9b3089548210b7116db34e269b5aa7192e6fd5516c6283405c3d1031c4f2590883dd633179562b75592a74ceceb1594e88be305c14aa7f0fedebf42f28d9c7feecc3b55c99492277948cf32c0067d5b9096f156951bb617e9e2b5b1891de261364ea169666534069f53d750f3f09fcc0d75966603c4fa6fd214c1c9837eb028bd1c6237b83d75d87155141f6a0723a39c0885417fc10eca5b09960c3c7fdc87b9d7827eec3053c3816d630340bf94d9f79d7266639c07d84ddc6ecaf26aa0f1a0d617f90bc01b8ae841b02fdc91',
 '64be3e0e846a87219ed35dd73ef79a6fc238ffae649e1b7b903effdf1d75db5c': '761a7bd5e1a1e53bb8a38f32c5eb1e48c2057d5809256008dd9fbce39e76e897023acd136553eb4d4429a7e6622d2cc42993985103f326b7c3fad4edeb2809d9b34889e50a2e66647b5895926a04b6311e3accf6dbd7a764f24a6284c46d8da2f79812c782c57a1a87d292bd8192012e36cb5dd921d458a10f9981d67f2eaf3bbcdb56f381a881e46244baf2a36506d2859a5cd5bbe06167f44d21788407ee29c6686d5142c1ba3922602b368eb8f2c80122b58ab0f78ab65f708406df992160ce628f47260879484004acdc81190184f6b5715e475825230be455ea9da933e4a44c5ae90e94bcba07b448c3597a2586100a6505dcebef6a0938acacf987e1ec',
 '6719768329512bd2be98c6124e688462747806dd70923ebcd39426442da39358': '69af306761466d7a8f1dd850ec461acb1aaa02d6537ae8b37f11fdd64a88c87f5b7a25d4215481a2c1003efa07b5eacc86e8c4f98b214ac0acf5eed1ad363b8dd1ffae050c8abf0a4df2e82a706a047141a621562c82188465c908b6ccb6827dcf7c45b4d9f67d6605dc5c632c60e56f62e157dd8e925953ddef171dcf670a061ae3ec85b62da86d1893070c4f80644a8a1a7ad70a6fc06122a9683b1042f4e8b4b699666924ec78bd7c45ed140b50e7a3fb9a7896540ae9d4d984a51b9e621cf7c06888c0886b808949555997c85917cefbcba3c087a2db50b333e36985951c4073811bc653fcc620a4f6ffcd987883cec5af27780921d6579f36b91399c47a',
 '7211fa32160b9d16a3ac5fcd4c4917c8c3a0506ae6f9a864c6507e4bf390485b': '3300fa46dae8cce8abfce993e438215ab1c526240cfec8f0a9a9905703cf32fdfd8be28ac54242c83ebcd3411b0545b46bc95be219c265c23cd785b9e07d0c39a6b5361562edf727aa268c20c42f9d1f328b21fa17488d41c506f62f1e157a9a34b7b0669d9a5b81ed507857dd3f05c35a39653cd5117ee27b993c0d5e535e288249d4d33aabb7e9859da104ebcb70aed539398740380bcf8571e84c3227538828a94600d74fc8ca5d40f0e59226d5145f30d74478116a6e12c5d2d577e83ac780bb1756b8b57dbf43276c9e47d3c67b92195b6dcf334f563680b7afcdd5c636e81dc206bca438a14bd4f960bfaff8f7e48d9ad6e6fcc8a05fc9af695867fac5',
 '74e3c7217def0234afa84d93c913125901d5d0cb5178c0a5bb7f6ff5b532f761': '4039a973f3179368d5099ab5073b7b1438132c276e790c7c3006c4f7cde9a7a894f095a2e67ccb9a66500ae7e77c003eb760b28ec2a20867ead5d0ace30030106aa4142183e1648fba01ccd0d53c52fd3776d88a6528608f57686a65af24a95d80f1aaabb6a6869da2b224c58c80ac4b06584567108a17cf490259f0716983007cc8c3627486278bf0e9f1954e3a78e3238ec0236840a5cd1a0672979711516b12d1ac71a134350710e64f073d3ffe80a172755f00a124b2e719903701d471823493b2d9a68494ef17a51ad185a4181f9ca433ebffbc233b29ace9fd6269ee5edaaa9f326c249baa0a5d3d38875a3aab25ba3fcf9968b792222984df71ed5f6b',
 '83d3791582781527120381cf77f776f609236c18954b6c617717450151c85007': '076247ef64138fb13cbd5cc191418c0dd91febb6fbd4eb0ebca6da9a42a9bf6914aaa448ce2071cd1f8a9c00aef96cbd96a0b00e54ebc7a703ad798e7b99b1b54f3acc048cedbafe69e97f1c9653898d0e03c52a91a1b956ec977a2c05d955f88f965336115ad263bb9176a094eb493867eda49e8ce2c55f0e97f2d8a219121973a31b9905acc6b67b2caac26f13941f2963c546cea82387a2c7573498fda6116ce68dfa2579589555617ab81ba741c11e82839b5eeb5118c32771b2b99f299047e1d9db101726265b8b07abc2d2f120925b211ba44c85f9c638655849c5a7321ab0141119d55b731bcdc7e499426aa259625869c4705ba68905dbfcdaaf4642',
 '90161162a627823fa42b0de818a7bc09f4eddd80a3a1b4637962c0f1bea6b7cf': '615135fc906dc3dbc5b0b243e9b95ba1f23de42c31c9ff797dfd9222f19399f5ced6d0816883844432856e93f4aebea0e34a17337b44ff1d2f6f300e40f34e0dc009dfd8e75cf768788da3342652f7657dda7ef5ccd7b539fe60fd239926710823807d4a2a6068670487ba1ecca9638cc0a87bfb4ede5027f8f9d4965c702414f5cd765ad422580df25d0e3919a5cb6552e7c03f7e29201f320eb123ea5bcfe41ce86323650325101feaaa178f6f36dc8db3748f215c10d79642ac8ff3b07ae5fe14d1ea1f08ddb204133e29c630464bc7c9be6ee14f467368244f3ac4c13f173d5645fc1cd01b8ba1caf85c42bf290519e4559ac00f4c2cb122707237eef1dd',
 '94e34946a13a6e9122626dd78724ac6fee4eb4cfa4d2105e3dcc673bb638aa4b': 'a6f0a6d5153ea0a392ae027ff41477489259e5da75e161ee87e296f8eaf8c1814512d5d720fbd676fc4909191b37928aafbcb87829bfedca16ce78fd59236306bb1617d653f3cebd1ef7627be5981c5eb700f4beee75ceec0ee371314fb1ad928bb16b0783eaa6215b3c3c93b3228095bf178319df60428970a5790b41a33c08809d5065d1462fbb3888b61e35e0df1f40d519c616cd9065db291db2c41de03e3f811151ea59fde11936c95ccd866193244560198ff8480862ac33fb4548e42a2abf5e7a4777b8b69430013b7b06837979de297550642605a374ded82b26057515de4df623382a8719470145acd323a87e8103dab2a2fcbbf8f4f356bf8bad26',
 '98f51cf2d5e64a5c57dfdf45ecb7340e975cac3e7f883005f0c649aac4844fb5': '5fdaabe347d88d363c12636105856e1e39256d879e17d5081ecdde7265fa9a1c915bbad9f32c580daf5ec281a411f85c5d7aa57f8be01ba1f000fe823832a908d984dc4f8aa045eabb7398a25fc25d43ed24bd5205b44f2ce33ddfc79d8bb7cce1d209827ac0fb9a75f541e94df67946ca3c77a6f7429cc7bbf097d1282417ef3a02569c05d1510ccab39b00325f2f15ce62ca194745c2a2bd30ef866f6f9ba1649219a96ae1c85b0bb347fbe71c80a292c92283c41095903b7086aab3d9a3a3379650af5a5545ac8295bd424bd74863bbbb50e637937cfbae687da0307b5d76b88ed311b81aa0e7202d7fa2ee10adc20595a40766bb5bd28d3bd2e63df84db8',
 'ae0e6d6e11e2a1f2a01fa0c59280ac0876ccf232691120abb766b695a1b522b3': '777459e44abe930e06ec71f31da309cd017c007e4989f936c05bd509cb28415e5b613a2e959f5fae9bfaa2510457b3f0f2afcf5b64e64bfcb56273cd5b9dfff9aa04e681e43a8d1f3e676c3ee2b6d5c4694d1b8febe6d7f78dae2e3e82056d11e42b80c73d4f2da01c06e09cacd8bfdf48af9fa9d774c1f0e7ca840e180beff914cc0f3dae1dbdd9cd7fea688154316c035d0983d19d289eed79fa071297b3f2bc89f04aa204ac0c209de8b8c9a9e9a2c72ea8d4819d7794726507520b6f6952500df16c357255e62f23a0499562c3d01c1905a4d33b3205497ad7ff8f81b2d6dc740eca4c1c91cdd0d3cd675ff9b8b615950bcebe0ba5b65626360ae055f8c8',
 'bd49938e8adbbf9afa7e442fded2b3ca93c36c46fd04e14c52c1e64c181ab3f5': '4723ecddbc67604f4b32d3d5c1be5d892994342905f540ec9afe5432807cc31798c159b5c0ea2b7ae1cedbf9c4f5f9a9bff11ab547035b5c5d4a51f227773f020bee7e50c77297ba529a70eb33924f48da5eaa58b2ca5e37c8d9094deb9a0c7245f99df6a474f316e119fd286629290df1643307094b6d65b3c9171506b23dfe1678527ff4611f2687171d8593bafb66bd3aad933dc7f8f3e0230a0de0887261b6e000c143b3e365abb3b5a5cd712b0444f51dcac901932c16c2345e293c06c03efc0324e93bb8345e9284537d7351ebe230b89df3b4f292cf8cd865bb6b0952dedaabd8a77a3598f2ac6642dd5c926981c4bc164e8e22a4653e441aff56d4bb',
 'cc851a882431fe7fc25bedb2ae824ebc5071200cb4f3659ea84290869a7dc8dc': '43bc1445d7a58ff206a36d73d930ec7485599f0692500cbf5c76fe24ceccef92c218b8d70ecfc65551a654bdb7f19b3e9c5e916e62fa1d1d30b1d80407f469d5c65fb966f5abf454c3f2b1dd2ddbf6af14cd28c1a7a105071528cc11d86de250003dda5be6affbac7400f896e9a0b24eb06f2c3a92e5e54650a94a97bc4cb58aeac4a4a43a2512755fa0d4518800f7962906d382b8593b222fd15993ae28a075041760c9935e7e23efca9a3abad9d6caa9385284ee30c87cc019c1084e29210bff0a6334189427d7b2d6cd556d6d05e5f8b15b6e16a7332884368acf3596d59e4f9c9b0faf45257472e52fc138c89dcff2d0f1130d65e629543e0900d0ab563a',
 'd42fb397cd552a04b0570f3ae60bebbd47cf65524885c820a58718a471d59ca9': 'a605e2c92542660c3da975637067bcadb91d462bae33d8e4e6b667c91eb75f6a7733f8a51f8f392a1e108ace7fc380191c05045affdbc220283be8576e1164396e5d9ae57f366b2221a8d88f47d7e6c15a8abdbeab5f0a73bb5d875607bfdb3df30195e8f20b06625048e8934c446fdf718f8e04ec0204fb9ad9c1e6c3ea74d6beeaaa2459b19d07dadb54e4f7f622d1da6e857359bf43791a08f9e840c304876378b698b004730524855df8c839de9c166241b7301057cc8f4ed1158c07be705cbfc539058369a31b9b88c2cf2d150021256ca5f295dd87b929398b1063a5b549b52e96db2a92954cd7fb6b9470aacaa590db923d22c53e9f7b3d102a399f23',
 'ed8fd6a1877d6b8d3060271b25979c812e8aa9d94b04ca09c090e87faacd6668': '443ae3e04f770c4a5cea3d4c91cf3cc39f7eae31a372ce81a720e5b1b61464f5484e990a0f667f62afe415235860a34cc931bfb95006d8ffd86d4f50721118d7b08b7be258373a081a0efc9d611f16e3aabb1703b258f0562096f20f9104194dbd0b109d731399c3928366e788bd1ba130f215e27cfa9b50b38a3d1a5da8eaa32ae06df5dec65a344f677cbf1ae22b9fcee68dbf46a87bcb527293ad6a254bf15660670503300fc9c3f46704a285a48c806be9424d4cdeae625840091fcb432e0d00f2846dca0d83e449d7780c6e8e92c685c2813467ae2ac6ff38f0afb7336f34b0a7aaf74bab796b81e60ffadd2c4d797e06a27b2ba26796eb7d3a4249430d',
 'fe8553ef528baf62b845ec6b1a785f0ac2c24fa46913106b0a2727379323a0b4': '32cba506369b005177c6b71d6aa56f2ee0c827baa321eeee514b9ba708958b7697cd420f55321d3db1c3da7a0cb92e8baddbf37d49bd6ad3ad84d60b500cf3a1ee62be54e2eae0086760fa57429a6300b375275a5f371e2bad04e1ee842dda645378f8709258be91494b133b7298d51a47948d533c78b816850d00f9ab55bb9e6e348a2b6a481376a7c4c9e0dfc6260ede195105fc051ddc776ccb8ac32b9f05ffa5d290e988d006c19d8d2a440f11230c9c681f7cc4da97d45867bd781ec9e0ee860bd6c8f126b078f90074c1e2f456fc09eb39a360a771c1d5b539092952f9904bfdb72941422fd4529a6ff3af58dfcf63effdb3c00c2d3bd28f2612599ae2',
 'ff34754657138c26584a250d1abf085019804bc742cc9f58371fd2c04129084c': '9abd24c1d1766791f0ccbb75083cb4f12240505ba85dd396d1ed3607e400bb2ba4d0a6e9283697b04111d4718003ce404fddd53dca58984bffdec0b1ba09b4bdcd280e95bb1a29dd45ec05df9542663571e6292476b40d0d94464dce2fc456298d7edce888da449a52c2dbd6989d261d5eb0325b8b7564ca81ae94bbc494a782c608c68f10383982676b5ab27eb89cdad538ee3f102c63234a7028f091a82cbcd796bfc25f69f92e4ab765ce2e1fa0080de2d31ef19a04dad0ab7b5a76ec9fdc37ccad87254b28bb9b67bea184a2953561d854d7c536b0ea228c9a09df53bc123861cac434bd6a15a56f682639ea604149b15f4c7b051016ae668322e7b6d9f8'}


TEST_AUTHORITY_SIGNATURES.update(
{'8a606adaf51bfaabca5c1fe23327c42730c64a7841ff2c14efbd428e917a0005': 'a2da3269dd03646196a8d8eb1c6ad773ddb61fb1c5554b3d6fa3331c3a692c32db8bee0168029cd34eed0e91a7ad0ed04de5c0f3570326f3d63cffccdbe31845c7497d22a57b5a0ce01ba0b819f597e09c42900e0796161762d964ec218daed331ac83416358c29b730d7f8b793e208d5764cbee1b9ab3ea1e94e0f83cb4b043dca0c807ec3378074963cc1598ee97b4f989cba74c8d9b7a86982162e42d86460f159b005ac83dd33fa2453de846a91000b2dfc62135799066b492e1aa8fbed250a20074f13d6936cc5383961d75b09ffa8abded8348749f46dcf615351145b43d5ca8bba04a3f1400532d25c30bd977d4d0c64c8b8d5c210eaa2eda496ac5d7',
 '928254c519ee823b5f2dcc144c1c992e06d694c3c753b395a0b3796ff98f983b': '689cd986487a4bb8658f758844fe9dfc7c89276ea0e3bdcf85c3d8b9e40a31463350e167863d691f4b109f76dd0eb758ae1d3b10cdf5ae65ba7b68f3e5421693be1d99481169b0589f5de49287ae1df9d731bb4364590ae11eb5e8dc1beab741dd3878d12fcd9cb191136aa89ca08bac9f2cc0420712f71e42093e5d377506baa2c1cecc73aa39ade095ce39d15b2b7d6374d1a04e2c80db70eef9e4dcf0c7d59ed7f7c45ff62a5d268e4960cedd78ad2179989f6c8d5b0e161d8149ff113bc3229c32c7a620bb48ce656682136f1d033c973bee8f5531b7ffab0ba0abd6e8b1fdd6788d54ee15366b57e028fcb56f8e92d1beb7dadcb02107d67e23b3f6bb9f',
 'ab6e341509e7e436f2c9e29f4671f65ba76e9f799350de84b8b73046f2e6bf49': '4096716d483a228d8e4905bb676639b1b9faa3782bcac3ddb0ff24742c0ffb2f282174e15f225e84ead618d12bb682f20be4eb673f2c955a664471a864fb1617a93f3e91bf0821f6c39d05e00952fad8d64f736939ba37b3b9ce328ede26b73d34c4e4c90f484cd57006a368d55450ed8188f9b8c6ebe4e23ec733ec692ebbd81763e375c9bb848375d4efe56f250287b9642258d43c3725daa97c491c08009b53fb24b605573c457702be1a52579603d4dd87fc531b01095b199a731934842b8493892c53c7bf3a7810f4438063449f0ad69c5161e4a3fb78782776c55f125e5de60636f59c55ebaac985624c6ca16dbad7b642e77ac35879bd92345a7284d4',
 'c10de51578b24f8d6a5db119506112b24fe022e16651d2a769711f493554f926': '3f5f1a7ecaaabdfaf0afb9480749f913a1b819cf558560146803fabf2a0ca6752c8aa701c47384252a1e02590e37cb4e5a55bd6822feefd5986fa6babdd3287e93eb1f696ebff01a6a9c46f3c7ab5f9c3589938bd42d2abcaec1c757ef90bef197f756161b64b73c07f0aa6ab93328872347e92970d116041a0788ed217d044adbff8917ab31082d388f9e27bfe873b050e5b8ab92eebde652becea7a0ca447ad3d17f7d303fa212e0c52d6916434e1c13a26affea08e2d85d489041744ba03695a6877a77d90d2f743db6795fded9aa2a4f46724d3f6b36a11eba22240c6fdab00260197b4b2123cbfc480716bf434701b676108ec2ffc92fdd20ab983ef932'}
)


TEST_AUTHORITY_SIGNATURES.update(
{'4d7db48e4fdd41511cee7eabc05ca3f126e1dc7fd523596c4efcfe1f4e27436f': '640562449ef922d90da9b3c6148df0d60355ce57d9714a943e59dc771fd16813d5f034f99fc2bc660079d894a63c09feba2c8242e97779c4b03936c9372344b2a1a009ffc517d25f3b1bcc870c07690c81c4a533ec792c1d946b6fa45c1eb14269e0fa5bd960e50347ee6606c6815a2c67b7d820ae965bdac3f48e3c038bd539713197157a190f6c170e595eacb5474b5df45c9b2205c3999547493eec021112887cc3e068d126956ed3302a2afeae9aba8f6a368ffb632b053b4b1b11d8856b6b4b4dda89c027c52bc9da9198bb267830b9a125709b7d36b08e6820d4503f9d2354a02f5532ae6a016a91e8df9c6f943ead40f34105364ae122f09e49a70aea',
 '7c209d0f3d1fc72a4eb7ff81d8bb7688dd14dee4c8f2abc555f803504d83d509': '02f80bfa6a7cf5ce7b6594e103747885071f13319871537d60f8687c47448c67edc4a9f373d89301aa6fd35dc5e17af6ff09636a176b08ff0da4f237adbf0728e97097ff81b6760f759c5c65a3817e690f27b8f1f5f85f4784775f3b2396c022682f24efd602c08584efc4e43b120ca515ac716edde27bd5d9ea371840891dc334d16ebcaab0181ca7a48fe4dd892eb5f21a27e0f85e27d36e19b7cab701d46850f9945441221ccc75e766a88a0d88eaece2d8da54394a9c44bb73b158e74b210487057d129ff0f64241e9a95b2b79125e1a96ef48ae667c25ea4e51b3bc24303d80483934a85a40c7ccc40047266e1ee6357acb3794774f3053e12fa417aae5',
 '81df0a93211512ee045416efeb7ed5a62ecf39d47ae93e0b063bf5ae31d28078': '5f5ef814689aa830f8eea2bf625209e1e5ae8db13394150792e4efd5d12c0ddae1dee37552e8c622020e5789116939fd7d2492d614da675001f73c86883822ad09c61d2efcc3e9316c299a7323a3cc0b312be35691653d454ba8061013260c7283289046fcc4c7794c205d380ee82b25fb595bec97ff245ed70e21ace853740dd2f62103ad0d9a58bab82175b72edf327a4f09e2cbe9864ade6649d2077b0eb5a8ac5c227268ab38eebbbe2abf3daa9add1809e8b98e2f54b22da381ec38de3d548dd3d8a7c6f9fb6aa484f040e44f3a5e47f9885b04c64f87fa314c1227e9610eec642cc04eea58216d79203ff631d158b7942842d1649cc7e45cf2af76464a',
 'fb8b85ebe57b76d7c75154f4003f0515e1489e7b72c9e2b5c32708d5f33dd20b': '79472cf60b21e80af1dc9562dd4bc6c1e2e05b9e1eef661e5e2346ce54757b324fed2fb0801a9b2e313bc14fe80720c358a0df0d37e928f514587ccde624446d34048a38774039831ab12b2055940a242afc70f502220f84155e598718541f410a26fdecaec709bfee28165e6785d3e2143a1b79f88d5caf0dbacb7cbd15964efeb986a5d214ffc4d9037cd15f48f5111bfd58ab6b968808b01d63d91570d29e187ca89566f6eeceea8827e819307c97889c7da03341e9c4c8abd560e2e4e6c1517732ba5cd2a1d98398646ccb1d5dde84f4af271111ad2e2e44cec64dbb7e2b39b2a8c9f0ee5b64ca0aec05bc47737c4e3acd2dba8357e9c7185b121f67219c'}
)


TEST_AUTHORITY_SIGNATURES.update(
{'0121b99bdeb058f85232cf00a89681ea10bbf27b4c2bd9348dfa1eb812391e52': '8789a9ea1a1acfa8f281d95136e038ce4d46ecaab01ae4ebb39fb886a043385318359cb920fd81d60610e12120c49d99416db50ee692f4d3f9f9803a38d440eb38bb15d74f2a204d51ad80eccfb2a91d97ce3d1007e7b5d25160c7f5ca264e661fb612d131ea8fc0306a3a29eb11a88b7323929a8278716af2cef55dca9f2f074d2d5265e4bc071dbf03e909e698bec2bb61e75d6a623ce31667de88d3b16e59cddb5934464d3e777a0822b14065ad2b402b2488148d4baa191b3e78cf4e29778f3fa9ef64b692b2a09c84d997239ad7d62dd5d0ffdd566b64ae0f5b5205270f6de772e1bee9c97afa873d87541ef5fc21320270466a3150013dd5c00fef1941',
 '60913bf7138a4dc30961e93e2a319c9a84b5104956d3d9304563e1df0e908ddd': '51ef82c0847348ee96356aa96be825799903f9839b4989a709345d90c2e285d8efc7f4431244dafede7549bd3bba1bfe20e1d6464ce67b8bb5542c2aeb1380154d6c59c7fdb87a587b9bf29a9b7bf34a9f80db9b048034784ae3ff4bcc9cf89c5f5640fb077b034854938ffbad0f201a488338ea19b6317eec41e15dc77db77406974519a0c962e52429014bd22b745995e4d065527612fc5048a084fd8abbe6b37d3d8193ea89fbd9123514a77a6e86646625e6f64e99f6fa00a8d27b1ce155f8556f2e1c6926e5728983128983518cbe45a582f4beab7ab86e523fe9315ac4975ed78d2aaa77b6854aeea1bfee67bccefe6406b495ca47f09b42290088c542',
 'c1e27e6ddcc84afb3e7ffe7267e6c2f5b12b7cbf07bea5b4e4900dd305986b1c': '6348eff5bd4cc2575cae2afbe236823205739c1428e4ff023eb9a5e316973c4868f52ffbfa3331c3ab403bb7d5a3db5d8319756c6200096bdfd605ea789e79f72489a60de90357b3f6b76dd9956bbb6585a93145face3d8fdc6356033cfb01af90c47e64b5c70ca860ca9cd0e2b2eae127d10beb64c46ed5b0a000b3aa9dcc894a787dc45cc48cf10a03c641c140dc3c640741cd85bf5cf51a28f7cb9ca7e1dd7f480865372b0533e990fab00b5a46dd26213191aea97e70ed34adace12885e6fcf20b63546e13f7078b74f65dbf1e0edbc8f2d9089ec86bf286a010518c85f33d694e5b63b9a2c8f337c3ff3682d348e2ab14b559dc76eae2faf466a98cd3a2'}
)


TEST_AUTHORITY_SIGNATURES.update(
{'066bfb96d15601db6df7060a565509577b7fb818021eac7d2954c759498e7ec9': '987e04100c9f5c2bf479b018af78b8083d972dd31a0e254f9b2bb1b9f5e1e3d9578d03a4b574b4576ff27aa8717126f780a3abe102221dfb0579ecc09b084bda0e958393423c589b48afb3f7b104aa0f4eeff63e9e317d06cbefc52270265a48ea369ad40f8aa003ae5053ee72629447567b4793a25e3e4358ee434fc9fb09f9f696f4b44edc028bcb6b23ea8130f904bb270a3efd70cc08cef2fd52252234d04d2111c441f33f7d6fe087f119cc980b205cdf4256a4b4e0097d3cd92668bbb07b9b21b4953f20b63c169313e051d6ff6c359a654922649e01ed3dbef98770f79d41e83f8bff8be63936f0468d733c121ee10fc5f50171549cd0bd413ce6791f'}
)


TEST_AUTHORITY_SIGNATURES.update(
{'b5da1391979f513b083c81a8ce355a0a649370f5b73e2f080ec30129b2715fe9': '741fb0963aff45de223e6b4a9b8c01a9ca6c86ac4b2c5fabb110f5d338b410c2e06d445f36e612bcc7fbd52e851005df932a70e2f85b5d0c5c9cb9e6189226c6bb0eeee1397d2b78635387490e6f31b8b1c363747f1802b491b871c85e87e0b81dc74cd0e582f3e7068da25af9c20502697e562742f274f2928224fe940388368fff93b2202945f3d734e969c50cb7bb0bccaef809d067771226479a79b442b5caaf45cd305298adfb6260629b5c79294f3ce0894c3881233d787dad1079b1c1873b93a6171155aebf1b08c948780b1f008ad992695444d65b9c23873cf5ea837d94c0a32264c84d29c806a621b16aeecd1771116bd2bca27e3c91550c8b13fb'}
)


TEST_AUTHORITY_SIGNATURES.update(
{'e751981bea6696cfc92ec2785abcd34ead6f2da58703557553346b26f92903f9': '7a8ebb54cd4207ea2e8fba9628eb271f77caa7fe2db7d7672ca71f157a7886da1ff5250a3130801293b70a2ba51cf1d67daffd4bc9144132d0e9e71db1d910f6212bb14d47c2e3085bdd1fe397f99e3128b67ee58b149c5cf0da1c6d372b3171b558b0084bc20fe4df2342a86986850d5b6130821282edea3ef5c4d3988e04efd0223bddc6af5cd7235f580ba68a7f31f46c1267ad7273ec6a6805bb41499a0afb6ce0dd13a53d3c67c206089bef1510d8f0a3d33b2f7a0701ca69825599163ec7382d4c6de22a78bb23e746129b6aa56e951cfaf4d7b0512f6a4375c8d1518dc5793140b7d70334ddd0243c0e0e34c146f3eee4739f39ced9570b5603cefa38'}
)


def payload_digest(payload):
    return hashlib.sha256(
        json.dumps(
            payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")
    ).hexdigest()


def refresh_quality_binding(check, authority, grader=DIGEST):
    evidence = check["evidence"]
    result_payload = {
        "artifact_sha256": evidence["artifact_sha256"],
        "artifact_source_id": evidence["artifact_source_id"],
        "critical": check["critical"],
        "evidence_kind": evidence["kind"],
        "id": check["id"],
        "max_score": check["max_score"],
        "passed": check["passed"],
        "schema_version": "quality-check-result.v1",
        "score": check["score"],
    }
    result_sha256 = payload_digest(result_payload)
    execution = {
        "authority_receipt_sha256": authority,
        "grader_sha256": grader,
        "evidence_artifact_sha256": evidence["artifact_sha256"],
        "artifact_source_id": evidence["artifact_source_id"],
        "result_sha256": result_sha256,
        "exit_code": 0,
    }
    receipt_payload = {
        "artifact_source_id": execution["artifact_source_id"],
        "authority_receipt_sha256": execution["authority_receipt_sha256"],
        "evidence_artifact_sha256": execution["evidence_artifact_sha256"],
        "exit_code": execution["exit_code"],
        "grader_sha256": execution["grader_sha256"],
        "result_sha256": execution["result_sha256"],
        "schema_version": "grader-execution-receipt.v1",
    }
    execution["receipt_sha256"] = payload_digest(receipt_payload)
    evidence["grader_execution"] = execution


def refresh_run_quality(run, authority):
    for check in run["quality_checks"]:
        refresh_quality_binding(check, authority, run["grader_sha256"])


def billed_thread(thread_id, kind, role, parent, credits):
    tokens = {
        "input_tokens": 100 if kind == "primary" else 0,
        "cached_input_tokens": 20 if kind == "primary" else 0,
        "cache_write_input_tokens": 0,
        "output_tokens": 30 if kind == "primary" else 0,
        "reasoning_output_tokens": 5 if kind == "primary" else 0,
        "total_tokens": 130 if kind == "primary" else 0,
    }
    return {
        "thread_id": thread_id,
        "kind": kind,
        "attempt": 1,
        "status": "completed",
        "role": role,
        "parent_thread_id": parent,
        "terminal": True,
        "cost_complete": True,
        "model": "test-primary" if kind == "primary" else "test-child",
        "effort": "medium" if kind == "primary" else "high",
        "service_tier": "default",
        "tokens": tokens,
        "credits": {
            "uncached_input": credits,
            "cached_input": "0",
            "output": "0",
            "total": credits,
        },
    }


def arm_evidence(arm, credits, identifier, authority):
    primary_id = f"{arm}-primary"
    child_id = f"{arm}-child"
    child_role = "explorer" if arm == "baseline" else "evidence_tester"
    artifact_source_id = f"sidecar://{identifier}/{arm}/grounded-result"
    artifact_sha256 = hashlib.sha256(artifact_source_id.encode("utf-8")).hexdigest()
    run = {
        "threads": [
            billed_thread(primary_id, "primary", "primary", None, credits),
            billed_thread(child_id, "child", child_role, primary_id, "0"),
        ],
        "expected_thread_ids": [primary_id, child_id],
        "expected_receiver_ids": [child_id],
        "process_exit_code": 0,
        "completion_status": "completed",
        "execution_index": 0,
        "wall_time_ms": 250,
        "child_count": 1,
        "retries": 0,
        "quality_checks": [
            {
                "id": "grounded-result",
                "passed": True,
                "critical": True,
                "score": 10,
                "max_score": 10,
                "evidence": {
                    "kind": "behavior",
                    "artifact_sha256": artifact_sha256,
                    "artifact_source_id": artifact_source_id,
                    "grader_execution": {},
                },
            }
        ],
        "scope_violations": [],
        "routing_violations": [],
        "routing_decision": "bounded specialist",
        "grader_sha256": DIGEST,
        "contamination_audit": {"passed": True, "notes": "clean"},
    }
    refresh_run_quality(run, authority)
    return run


def instance(identifier, family, *, holdout=False):
    arm_order = (
        ["custom", "baseline"]
        if identifier == "development-b"
        else ["baseline", "custom"]
    )
    authority = SEALED_AUTHORITY if holdout else DEVELOPMENT_AUTHORITY
    return {
        "instance_id": identifier,
        "task_class": "test-triage",
        "fixture_family": family,
        "fixture_sha256": hashlib.sha256(f"fixture:{identifier}".encode()).hexdigest(),
        "prompt_sha256": hashlib.sha256(f"prompt:{identifier}".encode()).hexdigest(),
        "rubric_sha256": RUBRIC_DIGEST,
        "scenario": f"scenario {identifier}",
        "expected_roles": ["evidence_tester"],
        "holdout": holdout,
        "arm_order": arm_order,
        "runs": {
            "baseline": arm_evidence("baseline", "10", identifier, authority),
            "custom": arm_evidence("custom", "9", identifier, authority),
        },
    }


def order_for(instances):
    return [
        {"instance_id": item["instance_id"], "arm": arm}
        for item in instances
        for arm in item["arm_order"]
    ]


def freeze_order(instances):
    execution_order = order_for(instances)
    for index, entry in enumerate(execution_order):
        selected = next(
            item for item in instances if item["instance_id"] == entry["instance_id"]
        )
        selected["runs"][entry["arm"]]["execution_index"] = index
    return execution_order


def campaign():
    instances = [
        instance("development-b", "family-b"),
        instance("development-a", "family-a"),
    ]
    return {
        "schema_version": 5,
        "campaign_id": "campaign-1",
        "configuration_hashes": {
            "role_instructions": DIGEST,
            "routing_policy": DIGEST,
            "task_fixtures": DIGEST,
            "graders": DIGEST,
            "grader_execution_authority_receipt": DEVELOPMENT_AUTHORITY,
            "pricing": DIGEST,
        },
        "allowed_baseline_roles": ["explorer"],
        "class_policies": {
            "test-triage": {
                "decision_mode": "elective",
                "custom_role": "evidence_tester",
            }
        },
        "execution_order": freeze_order(instances),
        "instances": instances,
    }


def holdout():
    instances = [instance("sealed-c", "family-c", holdout=True)]
    return {
        "schema_version": 5,
        "campaign_id": "campaign-1",
        "allowed_baseline_roles": ["explorer"],
        "seal": {
            "seal_id": "external-seal-1",
            "receipt_sha256": SEALED_AUTHORITY,
            "runner_sha256": DIGEST,
            "harness_sha256": DIGEST,
            "grader_sha256": DIGEST,
            "expected_answers_sha256": DIGEST,
            "fixtures_sha256": DIGEST,
            "prompts_sha256": DIGEST,
            "live_configuration_sha256": DIGEST,
            "agent_visibility_boundary_enforced": True,
            "runner_unlinked_before_agents": True,
        },
        "completion": {
            "receipt_sha256": SEALED_AUTHORITY,
            "results_sha256": DIGEST,
            "archive_sha256": DIGEST,
            "all_tested_threads_terminal_before_archive": True,
            "all_records_valid": True,
            "all_contamination_audits_clean": True,
        },
        "execution_order": freeze_order(instances),
        "instances": instances,
    }


def authority_payload_for(document, *, sealed=False):
    scope = "sealed" if sealed else "development"
    receipt = (
        document["seal"]["receipt_sha256"]
        if sealed
        else document["configuration_hashes"][
            "grader_execution_authority_receipt"
        ]
    )
    admissions = []
    for item in document["instances"]:
        for arm in sorted(("baseline", "custom")):
            run = item["runs"][arm]
            for check in run["quality_checks"]:
                evidence = check["evidence"]
                execution = evidence["grader_execution"]
                result = {
                    "schema_version": "quality-check-result.v1",
                    "artifact_sha256": evidence["artifact_sha256"],
                    "artifact_source_id": evidence["artifact_source_id"],
                    "critical": check["critical"],
                    "evidence_kind": evidence["kind"],
                    "id": check["id"],
                    "max_score": check["max_score"],
                    "passed": check["passed"],
                    "score": check["score"],
                }
                grader_receipt = {
                    "schema_version": "grader-execution-receipt.v1",
                    "artifact_source_id": execution["artifact_source_id"],
                    "authority_receipt_sha256": execution[
                        "authority_receipt_sha256"
                    ],
                    "evidence_artifact_sha256": execution[
                        "evidence_artifact_sha256"
                    ],
                    "exit_code": execution["exit_code"],
                    "grader_sha256": execution["grader_sha256"],
                    "result_sha256": execution["result_sha256"],
                }
                admissions.append(
                    {
                        "schema_version": "quality-evidence-admission.v1",
                        "campaign_id": document["campaign_id"],
                        "evidence_scope": scope,
                        "authority_receipt_sha256": receipt,
                        "instance_id": item["instance_id"],
                        "task_class": item["task_class"],
                        "fixture_sha256": item["fixture_sha256"],
                        "arm": arm,
                        "check_id": check["id"],
                        "artifact_sha256": evidence["artifact_sha256"],
                        "artifact_source_id": evidence["artifact_source_id"],
                        "grader_sha256": run["grader_sha256"],
                        "quality_result": result,
                        "quality_result_sha256": execution["result_sha256"],
                        "grader_execution_receipt": grader_receipt,
                        "grader_execution_receipt_sha256": execution[
                            "receipt_sha256"
                        ],
                    }
                )
    authority = {
        "schema_version": "quality-evidence-authority.v2",
        "campaign_id": document["campaign_id"],
        "campaign_sha256": payload_digest(document),
        "evidence_scope": scope,
        "authority_id": f"trusted-{scope}-harness",
        "authority_receipt_sha256": receipt,
        "admissions": admissions,
        "issuer_id": "evaluation-harness-2026",
        "key_id": "rsa-2026-08",
        "signature_algorithm": "rsa-pkcs1-v1_5-sha256",
    }
    return authority


def authority_for(document, *, sealed=False):
    authority = authority_payload_for(document, sealed=sealed)
    canonical = json.dumps(
        authority, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    digest = hashlib.sha256(canonical).hexdigest()
    try:
        authority["signature_hex"] = TEST_AUTHORITY_SIGNATURES[digest]
    except KeyError:
        authority["signature_hex"] = TEST_AUTHORITY_SIGNATURES[
            "21ba8b389182fd1289e47636a7f5251a1fa0b16870f4d5b1e5f25141631d6812"
        ]
    return authority


def validate_campaign(document, *, sealed_holdout=False, quality_authority=None):
    return _validate_campaign(
        document,
        sealed_holdout=sealed_holdout,
        quality_authority=(
            authority_for(document, sealed=sealed_holdout)
            if quality_authority is None
            else quality_authority
        ),
    )


def build_report(
    development,
    sealed=None,
    *,
    quality_authority=None,
    sealed_quality_authority=None,
):
    return _build_report(
        development,
        sealed,
        quality_authority=quality_authority or authority_for(development),
        sealed_quality_authority=(
            sealed_quality_authority
            or (authority_for(sealed, sealed=True) if sealed is not None else None)
        ),
    )


def set_run_credits(run, value):
    primary = next(item for item in run["threads"] if item["kind"] == "primary")
    primary["credits"]["uncached_input"] = value
    primary["credits"]["total"] = value


class EvaluationCampaignTest(unittest.TestCase):
    def test_paired_report_is_deterministic_and_exact(self):
        first = build_report(campaign(), holdout())
        reordered = campaign()
        reordered["instances"].reverse()
        second = build_report(reordered, holdout())
        self.assertEqual(first, second)

        task_class = first["task_classes"][0]
        self.assertEqual(task_class["recommendation"], "custom")
        self.assertEqual(task_class["arms"]["baseline"]["median_total_credits"], "10")
        self.assertEqual(task_class["arms"]["custom"]["median_total_credits"], "9")
        self.assertEqual(task_class["arms"]["custom"]["total_tokens"], 390)
        run = first["instances"][0]["arms"]["custom"]
        self.assertTrue(run["measurement_complete"])
        self.assertTrue(run["role_compliant"])
        self.assertTrue(run["routing_compliant"])
        self.assertFalse(run["recursion_detected"])
        self.assertEqual(run["total_tokens"], 130)
        child = next(item for item in run["threads"] if item["kind"] == "child")
        self.assertEqual(child["role"], "evidence_tester")
        self.assertEqual(child["parent_thread_id"], "custom-primary")

    def test_thread_attempt_declarations_reconcile_and_failed_retry_is_billed(self):
        missing = campaign()
        run = missing["instances"][0]["runs"]["baseline"]
        run["threads"] = run["threads"][:1]
        run["child_count"] = 0
        run["expected_receiver_ids"] = []
        with self.assertRaisesRegex(EvaluationError, "expected_thread_ids do not match"):
            validate_campaign(missing)

        mismatch = campaign()
        mismatch["instances"][0]["runs"]["baseline"]["retries"] = 1
        with self.assertRaisesRegex(EvaluationError, "does not match 0 recorded retry"):
            validate_campaign(mismatch)

        retried = campaign()
        run = retried["instances"][0]["runs"]["baseline"]
        run["threads"][1]["status"] = "failed"
        retry = copy.deepcopy(run["threads"][1])
        retry["attempt"] = 2
        retry["status"] = "completed"
        retry["tokens"]["output_tokens"] = 1
        retry["tokens"]["total_tokens"] = 1
        retry["credits"]["output"] = "0.5"
        retry["credits"]["total"] = "0.5"
        run["threads"].append(retry)
        run["retries"] = 1
        report = build_report(retried)
        measured = next(
            item for item in report["instances"] if item["instance_id"] == "development-b"
        )["arms"]["baseline"]
        self.assertEqual(measured["total_credits"], "10.5")
        self.assertEqual(measured["total_tokens"], 131)

    def test_external_quality_authority_rejects_self_recomputed_campaign_forgery(self):
        document = campaign()
        trusted_authority = authority_for(document)
        document["configuration_hashes"]["task_fixtures"] = "b" * 64
        target = document["instances"][0]
        target["fixture_sha256"] = "c" * 64
        check = target["runs"]["custom"]["quality_checks"][0]
        check["evidence"]["artifact_source_id"] = "sidecar://forged/source"
        check["evidence"]["artifact_sha256"] = hashlib.sha256(
            b"forged artifact"
        ).hexdigest()
        refresh_quality_binding(check, DEVELOPMENT_AUTHORITY)
        with self.assertRaisesRegex(
            EvaluationError, "campaign_sha256 does not match exact campaign"
        ):
            _validate_campaign(document, quality_authority=trusted_authority)

        missing = campaign()
        with self.assertRaisesRegex(EvaluationError, "requires a separate caller-supplied"):
            _validate_campaign(missing)
        duplicate = authority_for(campaign())
        duplicate["admissions"].append(copy.deepcopy(duplicate["admissions"][0]))
        with self.assertRaisesRegex(EvaluationError, "duplicate admission"):
            _validate_campaign(campaign(), quality_authority=duplicate)
        cross_campaign = authority_for(campaign())
        cross_campaign["campaign_id"] = "other-campaign"
        with self.assertRaisesRegex(EvaluationError, "does not match campaign"):
            _validate_campaign(campaign(), quality_authority=cross_campaign)
        type_invalid = authority_for(campaign())
        type_invalid["admissions"][0]["grader_execution_receipt"][
            "exit_code"
        ] = False
        with self.assertRaisesRegex(EvaluationError, "exit_code must be integer zero"):
            _validate_campaign(campaign(), quality_authority=type_invalid)

    def test_arm_order_balance_control_rejects_ten_to_one_skew(self):
        skewed = campaign()
        instances = []
        for index in range(11):
            item = instance(f"skew-{index}", f"family-{index}")
            item["arm_order"] = (
                ["custom", "baseline"]
                if index == 10
                else ["baseline", "custom"]
            )
            instances.append(item)
        skewed["instances"] = instances
        skewed["execution_order"] = freeze_order(instances)
        with self.assertRaisesRegex(EvaluationError, "arm order balance control failed"):
            _validate_campaign(skewed, quality_authority=authority_for(skewed))

        positive = build_report(campaign(), holdout())
        self.assertEqual(
            positive["overall_order_balance_control"]["decision"], "PASS"
        )
        self.assertEqual(
            positive["task_classes"][0]["order_balance_control"]["decision"],
            "PASS",
        )

    def test_package_anchored_signature_blocks_synchronized_authority_forgery(self):
        document = campaign()
        trusted = authority_for(document)
        forged_receipt = "c" * 64
        document["configuration_hashes"]["task_fixtures"] = "b" * 64
        document["configuration_hashes"][
            "grader_execution_authority_receipt"
        ] = forged_receipt
        document["instances"][0]["fixture_sha256"] = hashlib.sha256(
            b"forged fixture"
        ).hexdigest()
        for item in document["instances"]:
            for arm, run in item["runs"].items():
                check = run["quality_checks"][0]
                source = f"sidecar://forged/{item['instance_id']}/{arm}"
                check["evidence"]["artifact_source_id"] = source
                check["evidence"]["artifact_sha256"] = hashlib.sha256(
                    source.encode("utf-8")
                ).hexdigest()
                refresh_run_quality(run, forged_receipt)

        forged_authority = authority_payload_for(document)
        forged_authority["signature_hex"] = trusted["signature_hex"]
        with self.assertRaisesRegex(
            EvaluationError, "signature is invalid for the package-trusted issuer key"
        ):
            _validate_campaign(document, quality_authority=forged_authority)

        for field, value, message in (
            ("issuer_id", "unknown-issuer", "issuer_id is not package-trusted"),
            ("key_id", "unknown-key", "key_id is not package-trusted"),
            ("authority_id", "altered-authority", "signature is invalid"),
        ):
            altered = authority_for(campaign())
            altered[field] = value
            with self.subTest(field=field):
                with self.assertRaisesRegex(EvaluationError, message):
                    _validate_campaign(campaign(), quality_authority=altered)

        altered_signature = authority_for(campaign())
        altered_signature["signature_hex"] = (
            altered_signature["signature_hex"][:-1]
            + ("0" if altered_signature["signature_hex"][-1] != "0" else "1")
        )
        with self.assertRaisesRegex(EvaluationError, "signature is invalid"):
            _validate_campaign(campaign(), quality_authority=altered_signature)

        cross_scope = authority_for(campaign())
        cross_scope["evidence_scope"] = "sealed"
        with self.assertRaisesRegex(EvaluationError, "evidence_scope must be development"):
            _validate_campaign(campaign(), quality_authority=cross_scope)

    def test_execution_measurement_role_and_seal_mismatches_fail_closed(self):
        def nonterminal(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][1]["terminal"] = False

        def recursive(document, sealed):
            child = document["instances"][0]["runs"]["custom"]["threads"][1]
            child["parent_thread_id"] = child["thread_id"]

        def role_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][1]["role"] = "boundary_mapper"

        def token_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][0]["tokens"]["total_tokens"] = 999

        def cost_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][0]["credits"]["total"] = "999"

        def incomplete_cost(document, sealed):
            document["instances"][0]["runs"]["custom"]["threads"][0]["cost_complete"] = False

        def receiver_mismatch(document, sealed):
            document["instances"][0]["runs"]["custom"]["expected_receiver_ids"] = []

        def order_drift(document, sealed):
            document["execution_order"][0], document["execution_order"][1] = (
                document["execution_order"][1], document["execution_order"][0]
            )

        cases = (
            ("nonterminal", nonterminal, "nonterminal"),
            ("recursive", recursive, "recursive or unknown parent"),
            ("role", role_mismatch, "custom receiver role mismatch"),
            ("tokens", token_mismatch, "total must equal input plus output"),
            ("cost", cost_mismatch, "credits total does not match"),
            ("incomplete-cost", incomplete_cost, "unavailable cost evidence"),
            ("receiver", receiver_mismatch, "expected_receiver_ids do not match"),
            ("order", order_drift, "execution_order drifts"),
        )
        for name, mutate, message in cases:
            for input_name, factory, sealed in (
                ("development", campaign, False),
                ("sealed", holdout, True),
            ):
                with self.subTest(case=name, input=input_name):
                    document = factory()
                    mutate(document, sealed)
                    with self.assertRaisesRegex(EvaluationError, message):
                        validate_campaign(document, sealed_holdout=sealed)

        completion_mismatch = holdout()
        completion_mismatch["completion"]["archive_sha256"] = "b" * 64
        with self.assertRaisesRegex(EvaluationError, "archive hash does not match"):
            validate_campaign(completion_mismatch, sealed_holdout=True)
        invalid_completion = holdout()
        invalid_completion["completion"]["all_records_valid"] = False
        with self.assertRaisesRegex(EvaluationError, "all_records_valid must be true"):
            validate_campaign(invalid_completion, sealed_holdout=True)
        receipt_mismatch = holdout()
        receipt_mismatch["completion"]["receipt_sha256"] = "b" * 64
        with self.assertRaisesRegex(EvaluationError, "completion receipt hash does not match"):
            validate_campaign(receipt_mismatch, sealed_holdout=True)

    def test_routing_process_scope_quality_and_contamination_block_promotion(self):
        mutations = (
            lambda run: run["routing_violations"].append("wrong receiver"),
            lambda run: run.update(process_exit_code=1),
            lambda run: run.update(completion_status="failed"),
            lambda run: run["scope_violations"].append("escaped scope"),
            lambda run: run["quality_checks"][0].update(passed=False),
            lambda run: run["contamination_audit"].update(passed=False),
        )
        for arm in ("baseline", "custom"):
            for mutate in mutations:
                with self.subTest(arm=arm, mutation=mutate):
                    sealed = holdout()
                    run = sealed["instances"][0]["runs"][arm]
                    mutate(run)
                    refresh_run_quality(run, SEALED_AUTHORITY)
                    result = build_report(campaign(), sealed)["task_classes"][0]
                    self.assertEqual(result["recommendation"], "primary-default")
                    self.assertFalse(result["paired_integrity_passed"])

    def test_grader_and_rubric_comparability_remains_strict(self):
        mutations = (
            ("grader_sha256", "b" * 64, "paired grader_sha256 mismatch"),
            ("quality_checks.0.id", "other", "paired rubric mismatch"),
            ("quality_checks.0.critical", False, "paired rubric mismatch"),
            ("quality_checks.0.max_score", 11, "paired rubric mismatch"),
        )
        for path, value, message in mutations:
            document = campaign()
            run = document["instances"][0]["runs"]["custom"]
            if path == "grader_sha256":
                run[path] = value
            else:
                _, _, field = path.split(".")
                run["quality_checks"][0][field] = value
                refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
            with self.subTest(path=path):
                with self.assertRaisesRegex(EvaluationError, message):
                    validate_campaign(document)

        for document, sealed in ((campaign(), False), (holdout(), True)):
            for run in document["instances"][0]["runs"].values():
                run["grader_sha256"] = "b" * 64
            with self.subTest(frozen_grader="sealed" if sealed else "development"):
                with self.assertRaisesRegex(
                    EvaluationError, "run grader does not match frozen grader"
                ):
                    validate_campaign(document, sealed_holdout=sealed)

        unfrozen = campaign()
        for run in unfrozen["instances"][0]["runs"].values():
            run["quality_checks"][0]["max_score"] = 11
            refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
        with self.assertRaisesRegex(EvaluationError, "rubric_sha256 does not match"):
            validate_campaign(unfrozen)

    def test_quality_checks_require_bound_artifacts_and_verified_grader_execution(self):
        behavior = campaign()
        validate_campaign(behavior)

        prescribed = campaign()
        prescribed["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["kind"] = "prescribed-phrase"
        with self.assertRaisesRegex(EvaluationError, "must be behavior or source-fact"):
            validate_campaign(prescribed)

        unbound = campaign()
        execution = unbound["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["grader_execution"]
        execution["evidence_artifact_sha256"] = "b" * 64
        with self.assertRaisesRegex(EvaluationError, "does not bind evidence artifact"):
            validate_campaign(unbound)

        missing_source = campaign()
        missing_source["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["artifact_source_id"] = ""
        with self.assertRaisesRegex(EvaluationError, "must be a non-empty string"):
            validate_campaign(missing_source)

        self_filled = campaign()
        self_filled_execution = self_filled["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]["evidence"]["grader_execution"]
        self_filled_execution["result_sha256"] = "b" * 64
        self_filled_execution["receipt_sha256"] = "c" * 64
        with self.assertRaisesRegex(EvaluationError, "canonical check result"):
            validate_campaign(self_filled)

        changed_after_receipt = campaign()
        changed_check = changed_after_receipt["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]
        original_receipt = changed_check["evidence"]["grader_execution"][
            "receipt_sha256"
        ]
        changed_check["score"] = 9
        refresh_quality_binding(changed_check, DEVELOPMENT_AUTHORITY)
        changed_check["evidence"]["grader_execution"][
            "receipt_sha256"
        ] = original_receipt
        with self.assertRaisesRegex(EvaluationError, "canonical execution"):
            validate_campaign(changed_after_receipt)

        wrong_authority = campaign()
        wrong_authority_check = wrong_authority["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]
        refresh_quality_binding(wrong_authority_check, "b" * 64)
        with self.assertRaisesRegex(EvaluationError, "frozen external authority"):
            validate_campaign(wrong_authority)

        wrong_sealed_authority = holdout()
        wrong_sealed_check = wrong_sealed_authority["instances"][0]["runs"][
            "custom"
        ]["quality_checks"][0]
        refresh_quality_binding(wrong_sealed_check, DEVELOPMENT_AUTHORITY)
        with self.assertRaisesRegex(EvaluationError, "frozen external authority"):
            validate_campaign(wrong_sealed_authority, sealed_holdout=True)

        wrong_grader = campaign()
        wrong_grader_check = wrong_grader["instances"][0]["runs"]["custom"][
            "quality_checks"
        ][0]
        refresh_quality_binding(
            wrong_grader_check, DEVELOPMENT_AUTHORITY, grader="b" * 64
        )
        with self.assertRaisesRegex(EvaluationError, "does not match run grader"):
            validate_campaign(wrong_grader)

        unverified = campaign()
        unverified["instances"][0]["runs"]["custom"]["quality_checks"][0][
            "evidence"
        ]["grader_execution"]["exit_code"] = 1
        with self.assertRaisesRegex(EvaluationError, "exit_code must be integer zero"):
            validate_campaign(unverified)

        source_fact = campaign()
        for run in source_fact["instances"][0]["runs"].values():
            run["quality_checks"][0]["evidence"]["kind"] = "source-fact"
            refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
        signature = [("grounded-result", True, 10, "source-fact")]
        source_fact["instances"][0]["rubric_sha256"] = hashlib.sha256(
            json.dumps(signature, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        validate_campaign(source_fact)

        relabeled = copy.deepcopy(source_fact)
        for run in relabeled["instances"][0]["runs"].values():
            check = run["quality_checks"][0]
            original_receipt = check["evidence"]["grader_execution"][
                "receipt_sha256"
            ]
            check["evidence"]["kind"] = "behavior"
            refresh_quality_binding(check, DEVELOPMENT_AUTHORITY)
            check["evidence"]["grader_execution"][
                "receipt_sha256"
            ] = original_receipt
        with self.assertRaisesRegex(EvaluationError, "canonical execution"):
            validate_campaign(relabeled)

    def test_mandatory_named_gate_exception_is_narrow_and_fail_closed(self):
        base = campaign()
        base["class_policies"]["test-triage"] = {
            "decision_mode": "mandatory_named_gate",
            "custom_role": "evidence_tester",
            "higher_level_required": True,
            "callable_builtin_equivalent": False,
            "availability_probe_reference": "removal-probe-receipt",
            "availability_probe_sha256": DIGEST,
            "restored_after_probe": True,
        }
        sealed = holdout()
        for document in (base, sealed):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "9.14")
        mandatory = build_report(base, sealed)["task_classes"][0]
        self.assertEqual(mandatory["recommendation"], "retained-not-efficient")
        self.assertEqual(mandatory["governance_retention"]["decision"], "PASS")
        self.assertEqual(mandatory["efficiency_promotion"]["decision"], "BLOCK")

        elective = campaign()
        elective_holdout = holdout()
        for document in (elective, elective_holdout):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "9.14")
        self.assertEqual(
            build_report(elective, elective_holdout)["task_classes"][0]["recommendation"],
            "primary-default",
        )

        missing = copy.deepcopy(base)
        del missing["class_policies"]["test-triage"]["availability_probe_reference"]
        with self.assertRaisesRegex(EvaluationError, "missing=.*availability_probe_reference"):
            validate_campaign(missing)
        builtin = copy.deepcopy(base)
        builtin["class_policies"]["test-triage"]["callable_builtin_equivalent"] = True
        with self.assertRaisesRegex(EvaluationError, "callable_builtin_equivalent must be false"):
            validate_campaign(builtin)
        lower = copy.deepcopy(sealed)
        lower["instances"][0]["runs"]["custom"]["quality_checks"][0]["score"] = 8
        refresh_run_quality(
            lower["instances"][0]["runs"]["custom"], SEALED_AUTHORITY
        )
        self.assertEqual(
            build_report(base, lower)["task_classes"][0]["recommendation"],
            "primary-default",
        )

    def test_class_policy_role_cross_links_are_exact(self):
        overlap = campaign()
        overlap["allowed_baseline_roles"].append("evidence_tester")
        with self.assertRaisesRegex(EvaluationError, "overlap custom roles"):
            validate_campaign(overlap)

        extra_expected = campaign()
        extra_expected["instances"][0]["expected_roles"].append("boundary_mapper")
        extra_expected["instances"][0]["runs"]["custom"]["threads"].append(
            billed_thread(
                "custom-second-child",
                "child",
                "boundary_mapper",
                "custom-primary",
                "0",
            )
        )
        extra_expected["instances"][0]["runs"]["custom"]["expected_thread_ids"].append(
            "custom-second-child"
        )
        extra_expected["instances"][0]["runs"]["custom"]["expected_receiver_ids"].append(
            "custom-second-child"
        )
        extra_expected["instances"][0]["runs"]["custom"]["child_count"] = 2
        with self.assertRaisesRegex(EvaluationError, "expected_roles must exactly equal"):
            validate_campaign(extra_expected)

        sealed_role_drift = holdout()
        sealed_role_drift["instances"][0]["expected_roles"] = ["boundary_mapper"]
        sealed_role_drift["instances"][0]["runs"]["custom"]["threads"][1][
            "role"
        ] = "boundary_mapper"
        with self.assertRaisesRegex(EvaluationError, "expected_roles must exactly equal"):
            build_report(campaign(), sealed_role_drift)

    def test_sealed_boundary_and_external_cli(self):
        embedded = campaign()
        embedded["instances"].append(instance("leaked", "family-c", holdout=True))
        embedded["execution_order"] = freeze_order(embedded["instances"])
        with self.assertRaisesRegex(EvaluationError, "holdout must be false"):
            validate_campaign(embedded)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            campaign_path = root / "campaign.json"
            sealed_path = root / "private-sealed-results.json"
            authority_path = root / "development-quality-authority.json"
            sealed_authority_path = root / "sealed-quality-authority.json"
            report_path = root / "report.json"
            development = campaign()
            sealed = holdout()
            campaign_path.write_text(json.dumps(development), encoding="utf-8")
            sealed_path.write_text(json.dumps(sealed), encoding="utf-8")
            authority_path.write_text(
                json.dumps(authority_for(development)), encoding="utf-8"
            )
            sealed_authority_path.write_text(
                json.dumps(authority_for(sealed, sealed=True)), encoding="utf-8"
            )
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "evaluation", "report", "--campaign", str(campaign_path), "--quality-authority", str(authority_path), "--sealed-holdout", str(sealed_path), "--sealed-quality-authority", str(sealed_authority_path), "--output", str(report_path)],
                cwd=PACKAGE_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["task_classes"][0]["sealed_holdout_count"], 1)
            serialized = campaign_path.read_text() + sealed_path.read_text()
            self.assertNotIn("grader_logic", serialized)
            self.assertNotIn("expected_answer\"", serialized)

    def test_schema_artifacts_parse_and_forbid_unknown_fields(self):
        schema = json.loads((PACKAGE_ROOT / "evaluation" / "campaign.schema.json").read_text())
        sealed = json.loads((PACKAGE_ROOT / "evaluation" / "sealed-holdout.schema.json").read_text())
        production = json.loads(
            (PACKAGE_ROOT / "evaluation" / "production-fact.schema.json").read_text()
        )
        tiers = json.loads(
            (PACKAGE_ROOT / "evaluation" / "evidence-tier.schema.json").read_text()
        )
        authority = json.loads(
            (PACKAGE_ROOT / "evaluation" / "quality-authority.schema.json").read_text()
        )
        self.assertFalse(schema["additionalProperties"])
        self.assertFalse(schema["$defs"]["thread"]["additionalProperties"])
        self.assertFalse(sealed["additionalProperties"])
        self.assertFalse(production["additionalProperties"])
        self.assertFalse(production["properties"]["metrics"]["additionalProperties"])
        self.assertFalse(tiers["additionalProperties"])
        self.assertFalse(authority["additionalProperties"])
        self.assertFalse(authority["$defs"]["admission"]["additionalProperties"])
        self.assertEqual(schema["properties"]["schema_version"]["const"], 5)
        self.assertEqual(sealed["properties"]["schema_version"]["const"], 5)
        self.assertEqual(
            production["properties"]["schema_version"]["const"],
            "production-fact.v3",
        )
        self.assertEqual(
            authority["properties"]["schema_version"]["const"],
            "quality-evidence-authority.v2",
        )
        for field in (
            "campaign_sha256",
            "issuer_id",
            "key_id",
            "signature_algorithm",
            "signature_hex",
        ):
            self.assertIn(field, authority["required"])
        self.assertIn(
            "grader_execution_authority_receipt",
            schema["properties"]["configuration_hashes"]["required"],
        )
        evidence_schema = schema["$defs"]["check"]["properties"]["evidence"]
        self.assertIn("artifact_source_id", evidence_schema["required"])
        self.assertIn(
            "authority_receipt_sha256",
            evidence_schema["properties"]["grader_execution"]["required"],
        )
        self.assertEqual(
            evidence_schema["properties"]["kind"]["enum"],
            ["behavior", "source-fact"],
        )
        self.assertFalse(evidence_schema["additionalProperties"])
        self.assertFalse(
            evidence_schema["properties"]["grader_execution"]["additionalProperties"]
        )
        self.assertEqual(schema["$defs"]["thread"]["properties"]["kind"]["enum"], ["primary", "child"])

    def test_bundled_smoke_fixture_and_cli(self):
        examples = PACKAGE_ROOT / "evaluation" / "examples"
        development = json.loads((examples / "campaign.json").read_text())
        sealed = json.loads((examples / "sealed-holdout.json").read_text())
        development_authority = json.loads(
            (examples / "quality-authority-development.json").read_text()
        )
        sealed_authority = json.loads(
            (examples / "quality-authority-sealed.json").read_text()
        )
        report = build_report(
            development,
            sealed,
            quality_authority=development_authority,
            sealed_quality_authority=sealed_authority,
        )
        self.assertEqual(report["campaign_id"], "public-smoke")
        self.assertEqual(len(report["instances"]), 2)

        completed = subprocess.run(
            [sys.executable, "-B", "-m", "evaluation", "smoke"],
            cwd=PACKAGE_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("valid and deterministic", completed.stdout)

    def test_paired_pareto_blocks_pooled_quality_and_independent_median_tricks(self):
        pooled = campaign()
        pooled["instances"][0]["runs"]["custom"]["quality_checks"][0]["score"] = 9
        refresh_run_quality(
            pooled["instances"][0]["runs"]["custom"], DEVELOPMENT_AUTHORITY
        )
        for arm in ("baseline", "custom"):
            run = pooled["instances"][1]["runs"][arm]
            run["quality_checks"][0]["max_score"] = 100
        pooled["instances"][1]["runs"]["baseline"]["quality_checks"][0]["score"] = 1
        pooled["instances"][1]["runs"]["custom"]["quality_checks"][0]["score"] = 100
        for run in pooled["instances"][1]["runs"].values():
            refresh_run_quality(run, DEVELOPMENT_AUTHORITY)
        pooled["instances"][1]["rubric_sha256"] = "727ebd27e04a873a6e84043d1a71ade2060beffb668d26c6b2707e484ecb208d"
        result = build_report(pooled, holdout())["task_classes"][0]
        self.assertFalse(result["quality_non_regression"])
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        median_trick = campaign()
        sealed = holdout()
        pairs = [
            median_trick["instances"][0],
            median_trick["instances"][1],
            sealed["instances"][0],
        ]
        for item, baseline_cost, custom_cost in zip(
            pairs, ("0.01", "100", "100"), ("1", "90", "90"), strict=True
        ):
            set_run_credits(item["runs"]["baseline"], baseline_cost)
            set_run_credits(item["runs"]["custom"], custom_cost)
        result = build_report(median_trick, sealed)["task_classes"][0]
        self.assertEqual(result["arms"]["custom"]["median_total_credits"], "90")
        self.assertEqual(result["arms"]["baseline"]["median_total_credits"], "100")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")
        self.assertTrue(
            any(Decimal(value) > Decimal("1") for value in result["pair_credit_ratios"])
        )

    def test_duplicate_fixture_zero_baseline_and_cost_unavailability_fail_closed(self):
        duplicate = campaign()
        duplicate["instances"][1]["fixture_sha256"] = duplicate["instances"][0][
            "fixture_sha256"
        ]
        with self.assertRaisesRegex(EvaluationError, "duplicate fixture_sha256"):
            validate_campaign(duplicate)
        duplicate_prompt = campaign()
        duplicate_prompt["instances"][1]["prompt_sha256"] = duplicate_prompt[
            "instances"
        ][0]["prompt_sha256"]
        with self.assertRaisesRegex(EvaluationError, "duplicate prompt_sha256"):
            validate_campaign(duplicate_prompt)

        zero = campaign()
        set_run_credits(zero["instances"][0]["runs"]["baseline"], "0")
        result = build_report(zero, holdout())["task_classes"][0]
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        aggregate = campaign()
        aggregate_holdout = holdout()
        for document in (aggregate, aggregate_holdout):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "11")
        result = build_report(aggregate, aggregate_holdout)["task_classes"][0]
        self.assertGreater(Decimal(result["class_credit_ratio"]), Decimal("1"))
        self.assertGreater(Decimal(result["overall_credit_ratio"]), Decimal("1"))
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        unavailable = campaign()
        thread = unavailable["instances"][0]["runs"]["custom"]["threads"][0]
        thread["cost_complete"] = False
        thread["credits"] = {key: None for key in thread["credits"]}
        result = build_report(unavailable, holdout())["task_classes"][0]
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")
        self.assertIsNone(result["arms"]["custom"]["total_credits"])

    def test_positive_quality_requires_cost_non_regression_and_mandatory_dual_outcomes(self):
        improved = campaign()
        sealed = holdout()
        improved["instances"][0]["runs"]["baseline"]["quality_checks"][0]["score"] = 9
        refresh_run_quality(
            improved["instances"][0]["runs"]["baseline"], DEVELOPMENT_AUTHORITY
        )
        set_run_credits(improved["instances"][0]["runs"]["custom"], "11")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["quality_outcome"], "improved")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        set_run_credits(improved["instances"][0]["runs"]["custom"], "10")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["efficiency_promotion"]["decision"], "PASS")

        improved["class_policies"]["test-triage"] = {
            "decision_mode": "mandatory_named_gate",
            "custom_role": "evidence_tester",
            "higher_level_required": True,
            "callable_builtin_equivalent": False,
            "availability_probe_reference": "probe",
            "availability_probe_sha256": DIGEST,
            "restored_after_probe": True,
        }
        for document in (improved, sealed):
            for item in document["instances"]:
                set_run_credits(item["runs"]["baseline"], "30")
                set_run_credits(item["runs"]["custom"], "33")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["recommendation"], "retained-not-efficient")
        self.assertEqual(result["governance_retention"]["decision"], "PASS")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")

        for document in (improved, sealed):
            for item in document["instances"]:
                set_run_credits(item["runs"]["custom"], "30")
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["recommendation"], "retained-efficient")

        thread = improved["instances"][0]["runs"]["custom"]["threads"][0]
        thread["cost_complete"] = False
        thread["credits"] = {key: None for key in thread["credits"]}
        result = build_report(improved, sealed)["task_classes"][0]
        self.assertEqual(result["recommendation"], "retained-not-efficient")
        self.assertEqual(result["governance_retention"]["decision"], "PASS")
        self.assertEqual(result["efficiency_promotion"]["decision"], "BLOCK")


def evidence_document(tier, *, revision="abc123", package=DIGEST):
    provenance = {
        "implemented": {
            "source_tree_sha256": DIGEST,
            "diff_sha256": DIGEST,
            "implementation_receipt_sha256": DIGEST,
        },
        "verified-local": {
            "command": "python3 -B validate.py",
            "exit_code": 0,
            "environment_sha256": DIGEST,
            "result_sha256": DIGEST,
        },
        "verified-ci": {
            "provider": "github-actions",
            "run_id": "123",
            "run_url": "https://example.invalid/run/123",
            "revision": revision,
            "result_sha256": DIGEST,
        },
        "verified-target": {
            "target_id": "target-a",
            "environment_sha256": DIGEST,
            "revision": revision,
            "package_digest": package,
            "receipt_sha256": DIGEST,
        },
        "pilot-signed": {
            "authority": "deployment-owner",
            "authority_id": "owner-1",
            "signed_at": "2026-08-16T10:00:00+08:00",
            "signature_sha256": DIGEST,
            "target_receipt_sha256": DIGEST,
        },
    }[tier]
    return {
        "schema_version": "evidence-tier.v1",
        "tier": tier,
        "revision": revision,
        "package_digest": package,
        "artifact_digest": DIGEST,
        "predecessor": None,
        "provenance": provenance,
    }


def evidence_chain():
    chain = []
    for tier in ("implemented", "verified-local", "verified-ci", "verified-target", "pilot-signed"):
        document = evidence_document(tier)
        if chain:
            document["predecessor"] = {
                "tier": chain[-1]["tier"],
                "digest": canonical_digest(chain[-1]),
            }
        chain.append(document)
    return chain


class EvidenceTierTest(unittest.TestCase):
    def test_exact_monotonic_chain_and_cli(self):
        chain = evidence_chain()
        validate_evidence_chain(chain)
        with tempfile.TemporaryDirectory() as temporary:
            paths = []
            for index, document in enumerate(chain):
                path = Path(temporary) / f"{index}.json"
                path.write_text(json.dumps(document), encoding="utf-8")
                paths.extend(["--input", str(path)])
            completed = subprocess.run(
                [sys.executable, "-B", "-m", "evaluation", "evidence-tier", *paths],
                cwd=PACKAGE_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_missing_skipped_proxy_mismatch_and_authority_fail(self):
        cases = []
        missing = evidence_chain()[:2]
        missing[1]["predecessor"] = None
        cases.append((missing, "predecessor"))
        cases.append(([evidence_chain()[0], evidence_chain()[2]], "skips or reorders"))
        proxy = evidence_chain()[:2]
        proxy[1]["provenance"] = {"narrative": "verified locally"}
        cases.append((proxy, "keys mismatch"))
        mismatch = evidence_chain()[:3]
        mismatch[2]["revision"] = "different"
        cases.append((mismatch, "revision/package"))
        package_mismatch = evidence_chain()[:2]
        package_mismatch[1]["package_digest"] = "b" * 64
        cases.append((package_mismatch, "revision/package"))
        pilot = evidence_chain()
        del pilot[-1]["provenance"]["authority"]
        cases.append((pilot, "keys mismatch"))
        target_receipt_mismatch = evidence_chain()
        target_receipt_mismatch[-1]["provenance"]["target_receipt_sha256"] = "b" * 64
        cases.append((target_receipt_mismatch, "does not match verified-target receipt"))
        for chain, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(EvaluationError, message):
                    validate_evidence_chain(chain)


def uuid7_for(moment):
    milliseconds = int(moment.timestamp() * 1000)
    return str(uuid.UUID(int=(milliseconds << 80) | (7 << 76) | (2 << 62) | 1))


def write_jsonl(path, events):
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


class ProductionFactsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Test"], check=True)
        (self.repo / "tracked.txt").write_text("base\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "base"], check=True)
        self.base = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        self.parent = self.root / "parent.jsonl"
        self.children = self.root / "children"
        self.children.mkdir()
        self.spawn = datetime(2026, 8, 16, 1, 0, tzinfo=timezone.utc)
        self.child_id = uuid7_for(self.spawn.replace(microsecond=1000))
        self._write_valid_sources()

    def tearDown(self):
        self.temporary.cleanup()

    def _write_valid_sources(self, *, fork_turns="all", extra_parent=(), extra_child=()):
        call_id = "spawn-1"
        write_jsonl(
            self.parent,
            [
                {"timestamp": self.spawn.isoformat(), "type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": call_id, "arguments": json.dumps({"task_name": "worker__fact", "fork_turns": fork_turns})}},
                {"timestamp": self.spawn.replace(microsecond=500).isoformat(), "type": "response_item", "payload": {"type": "function_call_output", "call_id": call_id, "output": json.dumps({"agent_id": self.child_id})}},
                {"timestamp": self.spawn.replace(microsecond=700).isoformat(), "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 1, "cached_input_tokens": 0, "cache_write_input_tokens": 0, "output_tokens": 1, "reasoning_output_tokens": 0, "total_tokens": 2}}}},
                {"timestamp": self.spawn.replace(microsecond=800).isoformat(), "type": "event_msg", "payload": {"type": "billing_record", "scope": "thread", "thread_id": "parent-thread", "credits": {"uncached_input": "3", "cached_input": "1", "output": "2", "total": "6"}}},
                {"timestamp": self.spawn.replace(microsecond=900).isoformat(), "type": "event_msg", "payload": {"type": "billing_record", "scope": "run", "run_id": "run-1", "credits": {"uncached_input": "5", "cached_input": "1", "output": "4", "total": "10"}}},
                *extra_parent,
            ],
        )
        start = self.spawn.replace(microsecond=2000)
        write_jsonl(
            self.children / f"{self.child_id}.jsonl",
            [
                {"timestamp": self.spawn.replace(microsecond=1000).isoformat(), "type": "session_meta", "payload": {"id": self.child_id}},
                {"timestamp": start.isoformat(), "type": "turn_context", "payload": {"role": "worker"}},
                {"timestamp": self.spawn.replace(microsecond=3000).isoformat(), "type": "event_msg", "payload": {"type": "token_count", "info": {"total_token_usage": {"input_tokens": 10, "cached_input_tokens": 2, "cache_write_input_tokens": 0, "output_tokens": 4, "reasoning_output_tokens": 1, "total_tokens": 14}}}},
                *extra_child,
                {"timestamp": self.spawn.replace(microsecond=4000).isoformat(), "type": "event_msg", "payload": {"type": "billing_record", "scope": "thread", "thread_id": self.child_id, "credits": {"uncached_input": "2", "cached_input": "0", "output": "2", "total": "4"}}},
                {"timestamp": self.spawn.replace(microsecond=5000).isoformat(), "type": "event_msg", "payload": {"type": "agent_status", "status": "completed"}},
            ],
        )

    def _extract(self, state="terminal"):
        return extract_production_facts(
            parent=self.parent,
            children_root=self.children,
            repo=self.repo,
            base=self.base,
            cutoff=datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc),
            source_state=state,
        )

    def test_terminal_fact_is_private_typed_and_complete(self):
        fact = self._extract()
        self.assertEqual(fact["schema_version"], "production-fact.v3")
        self.assertFalse(fact["completion_claim_eligible"])
        self.assertFalse(fact["causal_claim_eligible"])
        self.assertFalse(fact["promotion_claim_eligible"])
        observational_laundering = copy.deepcopy(fact)
        observational_laundering["completion_claim_eligible"] = True
        with self.assertRaisesRegex(EvaluationError, "observational production facts"):
            validate_production_fact(observational_laundering)
        self.assertEqual(fact["metrics"]["forks"]["all"]["value"], 1)
        serialized = json.dumps(fact)
        self.assertNotIn(str(self.root), serialized)
        self.assertNotIn(self.child_id, serialized)
        for item in fact["metrics"]["tokens"].values():
            self.assertEqual(item["status"], "available")
            self.assertIsNotNone(item["basis"])
            self.assertIsNotNone(item["source_id"])
        for item in fact["metrics"]["credits"].values():
            self.assertEqual(item["status"], "available")
        self.assertEqual(fact["metrics"]["credits"]["thread_total"]["value"], "10")
        self.assertEqual(fact["metrics"]["credits"]["run_total"]["value"], "10")
        child_raw = next(self.children.iterdir()).read_bytes()
        session_meta_size = len(child_raw.splitlines(keepends=True)[0])
        self.assertEqual(
            fact["metrics"]["log_bytes"]["children"]["value"],
            len(child_raw) - session_meta_size,
        )
        self.assertEqual(
            fact["metrics"]["log_bytes"]["total"]["value"],
            fact["metrics"]["log_bytes"]["parent"]["value"]
            + fact["metrics"]["log_bytes"]["children"]["value"],
        )
        child_path = next(self.children.iterdir())
        child_path.write_text(
            child_path.read_text(encoding="utf-8")
            + json.dumps(
                {
                    "timestamp": "2026-08-16T03:00:00+00:00",
                    "type": "event_msg",
                    "payload": {"type": "after-cutoff"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        rebound = self._extract()
        self.assertNotEqual(fact["sources"]["child_sha256"], rebound["sources"]["child_sha256"])
        for key in ("parent", "children", "total"):
            self.assertEqual(
                fact["metrics"]["log_bytes"][key]["value"],
                rebound["metrics"]["log_bytes"][key]["value"],
            )
        output = self.root / "fact.json"
        completed = subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "evaluation",
                "production-facts",
                "--parent",
                str(self.parent),
                "--children-root",
                str(self.children),
                "--repo",
                str(self.repo),
                "--base",
                self.base,
                "--cutoff",
                "2026-08-16T02:00:00+00:00",
                "--source-state",
                "terminal",
                "--output",
                str(output),
            ],
            cwd=PACKAGE_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(output.read_text())["schema_version"], "production-fact.v3")

    def test_unrelated_supported_event_token_names_do_not_change_usage(self):
        baseline = self._extract()
        injected = {
            "timestamp": self.spawn.replace(microsecond=3500).isoformat(),
            "type": "event_msg",
            "payload": {
                "type": "progress",
                "unrelated": {
                    "input_tokens": 999999,
                    "cached_input_tokens": 999999,
                    "cache_write_input_tokens": 999999,
                    "output_tokens": 999999,
                    "reasoning_output_tokens": 999999,
                    "total_tokens": 1999998,
                },
            },
        }
        self._write_valid_sources(extra_child=(injected,))
        observed = self._extract()
        self.assertEqual(
            {
                key: metric["value"]
                for key, metric in baseline["metrics"]["tokens"].items()
            },
            {
                key: metric["value"]
                for key, metric in observed["metrics"]["tokens"].items()
            },
        )

    def test_billing_records_require_event_msg_outer_envelope(self):
        parent_events = [
            json.loads(line) for line in self.parent.read_text().splitlines()
        ]
        thread_record = next(
            event
            for event in parent_events
            if event.get("payload", {}).get("type") == "billing_record"
            and event["payload"].get("scope") == "thread"
        )
        thread_record["type"] = "session_meta"
        write_jsonl(self.parent, parent_events)
        fact = self._extract()
        self.assertEqual(fact["unsupported_event_count"]["value"], 1)
        self.assertTrue(
            all(
                metric["status"] == "unavailable" and metric["value"] is None
                for metric in fact["metrics"]["credits"].values()
            )
        )

    def test_git_denominator_sources_bind_base_and_staged_state(self):
        clean = self._extract()
        (self.repo / "tracked.txt").write_text("base\ncommitted\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "tracked.txt"], check=True
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "-qm", "second"], check=True
        )
        head = subprocess.run(
            ["git", "-C", str(self.repo), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
        old_base = self._extract()
        head_base = extract_production_facts(
            parent=self.parent,
            children_root=self.children,
            repo=self.repo,
            base=head,
            cutoff=datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc),
            source_state="terminal",
        )
        self.assertEqual(old_base["git_source"]["head_revision"], head_base["git_source"]["head_revision"])
        self.assertNotEqual(
            old_base["metrics"]["git_denominators"]["commit_count"]["source_id"],
            head_base["metrics"]["git_denominators"]["commit_count"]["source_id"],
        )

        (self.repo / "tracked.txt").write_text(
            "base\ncommitted\nstaged\n", encoding="utf-8"
        )
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "tracked.txt"], check=True
        )
        staged = self._extract()
        self.assertEqual(old_base["git_source"]["head_revision"], staged["git_source"]["head_revision"])
        for name, metric in old_base["metrics"]["git_denominators"].items():
            if metric["status"] == "available":
                self.assertNotEqual(
                    metric["source_id"],
                    staged["metrics"]["git_denominators"][name]["source_id"],
                    name,
                )
        forged = copy.deepcopy(staged)
        forged["metrics"]["git_denominators"]["commit_count"]["source_id"] = (
            clean["metrics"]["git_denominators"]["commit_count"]["source_id"]
        )
        with self.assertRaisesRegex(
            EvaluationError, "does not bind complete Git denominator state"
        ):
            validate_production_fact(forged)

    def test_git_denominator_sources_bind_repository_identity(self):
        first = self._extract()
        repeated = self._extract()
        self.assertEqual(
            first["metrics"]["git_denominators"]["commit_count"]["source_id"],
            repeated["metrics"]["git_denominators"]["commit_count"]["source_id"],
        )

        clone = self.root / "repo-clone"
        subprocess.run(
            ["git", "clone", "-q", "--no-hardlinks", str(self.repo), str(clone)],
            check=True,
        )
        cloned = extract_production_facts(
            parent=self.parent,
            children_root=self.children,
            repo=clone,
            base=self.base,
            cutoff=datetime(2026, 8, 16, 2, 0, tzinfo=timezone.utc),
            source_state="terminal",
        )
        self.assertEqual(
            first["git_source"]["head_revision"], cloned["git_source"]["head_revision"]
        )
        self.assertNotEqual(
            first["sources"]["repo_path_sha256"], cloned["sources"]["repo_path_sha256"]
        )
        for name, metric in first["metrics"]["git_denominators"].items():
            if metric["status"] == "available":
                self.assertNotEqual(
                    metric["source_id"],
                    cloned["metrics"]["git_denominators"][name]["source_id"],
                    name,
                )

    def test_copied_history_active_dirty_unsupported_nested_and_failed_spawn(self):
        copied = {"timestamp": "2026-08-16T00:59:59+00:00", "type": "turn_context", "payload": {"role": "primary"}}
        self._write_valid_sources(extra_child=(copied,))
        with self.assertRaisesRegex(EvaluationError, "copied pre-spawn"):
            self._extract()

        self._write_valid_sources(extra_parent=({"timestamp": self.spawn.replace(microsecond=4000).isoformat(), "type": "future_event", "payload": {}},))
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        fact = self._extract("active")
        self.assertFalse(fact["causal_claim_eligible"])
        self.assertFalse(fact["git_source"]["clean"])
        self.assertEqual(fact["unsupported_event_count"]["value"], 1)
        (self.repo / "dirty.txt").unlink()

        nested_id = uuid7_for(self.spawn.replace(microsecond=4000))
        nested = (
            {"timestamp": self.spawn.replace(microsecond=3500).isoformat(), "type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": "nested", "arguments": json.dumps({"task_name": "nested"})}},
            {"timestamp": self.spawn.replace(microsecond=3600).isoformat(), "type": "response_item", "payload": {"type": "function_call_output", "call_id": "nested", "output": json.dumps({"agent_id": nested_id})}},
        )
        self._write_valid_sources(extra_child=nested)
        fact = self._extract()
        self.assertEqual(fact["metrics"]["spawns"]["nested"]["value"], 1)
        self.assertFalse(fact["promotion_claim_eligible"])

        for path in self.children.iterdir():
            path.unlink()
        write_jsonl(
            self.parent,
            [
                {"timestamp": self.spawn.isoformat(), "type": "response_item", "payload": {"type": "function_call", "name": "spawn_agent", "call_id": "failed", "arguments": json.dumps({"task_name": "failed"})}},
                {"timestamp": self.spawn.replace(microsecond=1000).isoformat(), "type": "response_item", "payload": {"type": "function_call_output", "call_id": "failed", "is_error": True, "output": "failed to spawn"}},
            ],
        )
        fact = self._extract()
        self.assertEqual(fact["metrics"]["spawns"]["failed"]["value"], 1)
        self.assertFalse(fact["completion_claim_eligible"])

    def test_child_lineage_requires_unique_ordered_earliest_turn_context(self):
        child_path = next(self.children.iterdir())
        events = [json.loads(line) for line in child_path.read_text().splitlines()]
        events[1]["timestamp"] = self.spawn.replace(microsecond=3000).isoformat()
        events.insert(
            2,
            {
                "timestamp": self.spawn.replace(microsecond=2000).isoformat(),
                "type": "turn_context",
                "payload": {"role": "worker"},
            },
        )
        write_jsonl(child_path, events)
        with self.assertRaisesRegex(EvaluationError, "lineage is out of order"):
            self._extract()

        self._write_valid_sources()
        child_path = next(self.children.iterdir())
        events = [json.loads(line) for line in child_path.read_text().splitlines()]
        events.insert(2, copy.deepcopy(events[1]))
        write_jsonl(child_path, events)
        with self.assertRaisesRegex(EvaluationError, "lineage start is ambiguous"):
            self._extract()

        self._write_valid_sources()
        self.assertFalse(self._extract()["completion_claim_eligible"])

    def test_metric_status_equivalence_and_divergent_git(self):
        with self.assertRaisesRegex(EvaluationError, "available metric"):
            _metric(1, None, None)
        with self.assertRaisesRegex(EvaluationError, "unavailable metric"):
            _metric(None, "basis", "source")
        fact = self._extract()
        numeric_unavailable = copy.deepcopy(fact)
        numeric_unavailable["metrics"]["tokens"]["total_tokens"]["status"] = "unavailable"
        with self.assertRaisesRegex(EvaluationError, "unavailable status requires null"):
            validate_production_fact(numeric_unavailable)
        null_available = copy.deepcopy(fact)
        null_available["metrics"]["tokens"]["total_tokens"]["value"] = None
        with self.assertRaisesRegex(EvaluationError, "available status requires non-null"):
            validate_production_fact(null_available)
        subprocess.run(["git", "-C", str(self.repo), "checkout", "-q", "--orphan", "divergent"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "rm", "-q", "-f", "tracked.txt"], check=True)
        (self.repo / "other.txt").write_text("other\n", encoding="utf-8")
        subprocess.run(["git", "-C", str(self.repo), "add", "other.txt"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "divergent"], check=True)
        fact = self._extract()
        self.assertFalse(fact["git_source"]["base_is_ancestor"])
        self.assertFalse(fact["causal_claim_eligible"])

    def test_credit_records_fail_closed_and_never_derive_from_tokens(self):
        source_paths = [self.parent, *self.children.iterdir()]
        for path in source_paths:
            events = [json.loads(line) for line in path.read_text().splitlines()]
            write_jsonl(
                path,
                [
                    event
                    for event in events
                    if event.get("payload", {}).get("type") != "billing_record"
                ],
            )
        fact = self._extract()
        self.assertTrue(
            all(
                metric["status"] == "unavailable" and metric["value"] is None
                for metric in fact["metrics"]["credits"].values()
            )
        )
        self.assertTrue(
            all(metric["status"] == "available" for metric in fact["metrics"]["tokens"].values())
        )
        self.assertFalse(fact["promotion_claim_eligible"])

        self._write_valid_sources()
        child_path = next(self.children.iterdir())
        child_events = [json.loads(line) for line in child_path.read_text().splitlines()]
        billing = next(
            event
            for event in child_events
            if event.get("payload", {}).get("type") == "billing_record"
        )
        child_events.insert(-1, copy.deepcopy(billing))
        write_jsonl(child_path, child_events)
        ambiguous = self._extract()
        self.assertTrue(
            all(
                metric["status"] == "unavailable"
                for metric in ambiguous["metrics"]["credits"].values()
            )
        )
        self.assertFalse(ambiguous["promotion_claim_eligible"])

        self._write_valid_sources()
        parent_events = [json.loads(line) for line in self.parent.read_text().splitlines()]
        run_record = next(
            event
            for event in parent_events
            if event.get("payload", {}).get("scope") == "run"
        )
        run_record["payload"]["credits"]["uncached_input"] = "6"
        run_record["payload"]["credits"]["total"] = "11"
        write_jsonl(self.parent, parent_events)
        with self.assertRaisesRegex(EvaluationError, "do not match complete thread"):
            self._extract()


if __name__ == "__main__":
    unittest.main()
