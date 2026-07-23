import asyncio
import re
import os
import random
from datetime import datetime
from nostr_sdk import Client, Keys, PublicKey, Filter, EventBuilder, NostrSigner, Kind, RelayUrl, HandleNotification, NostrWalletConnectUri, Nwc
from dotenv import load_dotenv
from nosrandom import nosrandom

load_dotenv()
nsec = os.getenv("NOSTR_NSEC")

TARGET_KEYWORD = "やみ"

TARGET_NPUB = os.getenv("NOSTR_TARGET_NPUB")

# 1. 「やみ」キーワード用パターン
COMMAND_PATTERN = re.compile(rf"{re.escape(TARGET_KEYWORD)}([,、\s ]?)(.*)", re.IGNORECASE | re.DOTALL)

# 2. メンション用パターン（先頭にある nostr:npub1... や @メンション名 + 区切り文字 + 本文）
MENTION_PATTERN = re.compile(r"^(?:nostr:npub1[a-z0-9]+|@\w+|@[^\s,、]+)([,、\s ]?)(.*)", re.IGNORECASE | re.DOTALL)

NWC_URI_STR = os.getenv("NOSTR_NWC_URI")
PRAISE_KEYWORDS = ["かわいい", "天才", "すごい", "神", "優秀", "えらい", "好き", "最高"]

def check_praise_and_zap_trigger(cmd_text: str, probability: float = 0.01) -> bool:
    is_praised = any(keyword in cmd_text.lower() for keyword in PRAISE_KEYWORDS)
    return is_praised and (random.random() < probability)

async def send_zap_via_nwc(target_event, sats: int = 21):
    try:
        uri = NostrWalletConnectUri.parse(NWC_URI_STR)
        nwc = Nwc(uri)
        
        comment = "これ、受け取ってくれるかな？、、、"
        msats = sats * 1000
        
        await nwc.zap_event(target_event, msats, comment)
        print(f"NWC経由で{sats}SatsのZap送信に成功しました！")
        return True
    
    except Exception as e:
        print(f"Zap送信失敗 (NWCエラーまたは相手のLNURL未設定): {e}")
        return False

class MyNotificationHandler(HandleNotification):
    def __init__(self, client, my_pubkey):
        super().__init__()
        self.client = client
        self.my_pubkey = my_pubkey
        
        try:
            self.target_hex_pubkey = PublicKey.parse(TARGET_NPUB).to_hex()
            print(f"npubが指定されました: {self.target_hex_pubkey}")
        except Exception:
            self.target_hex_pubkey = None
            
        self.is_bot_active = True

    async def handle(self, relay_url, subscription_id, event):
        # 自分自身の投稿は無視
        if event.author() == self.my_pubkey:
            return

        author_hex = event.author().to_hex()
        text = event.content()
        my_hex_pubkey = self.my_pubkey.to_hex()

        # -------------------------------------------------------------
        # メンション判定 (イベントのタグ内に自分の pubkey があるか)
        # -------------------------------------------------------------
        is_mentioned = False
        for tag in event.tags().to_vec():
            tag_vec = tag.as_vec()
            if len(tag_vec) >= 2 and tag_vec[0] == "p" and tag_vec[1] == my_hex_pubkey:
                is_mentioned = True
                break

        delimiter = None
        prompt_text = None
        matched = False

        # --- A. メンションの場合 ---
        if is_mentioned:
            match = MENTION_PATTERN.search(text.strip())
            if match:
                delimiter = match.group(1)
                prompt_text = match.group(2)
            else:
                # 明確な @表記 や nostr:npub が先頭にないメンション（タグのみ等）の場合
                delimiter = ""
                prompt_text = text
            matched = True

        # --- B. メンションではなく「やみ」キーワードの場合 ---
        else:
            match = COMMAND_PATTERN.search(text)
            if match:
                delimiter = match.group(1)
                prompt_text = match.group(2)
                matched = True

        # --- やみ 睡眠管理 ---
        if not matched or prompt_text is None:
            return
        
        cmd = prompt_text.strip()
        
        if self.target_hex_pubkey and author_hex == self.target_hex_pubkey:
            if "おはよう" in cmd:
                self.is_bot_active = True
                print("やみを開始しました")
            elif "おやすみ" in cmd:
                pass
            
        if not self.is_bot_active:
            return

        # --- 各種関数 ---
        def roll_dice() -> str:
            resp = [
                f"サイコロを振ったよ: [{nosrandom(1, 6)}]だった、、、よ",
                f"サイコロを振ったよ、、、ごめん机の下に入っちゃった、、、",
                f"サイコロ「今日は非番やで」",
                f"サイコロなくしちゃった、、、",
            ]
            return random.choice(resp)
        
        def chinchiro() -> str:
            a = nosrandom(1, 6)
            b = nosrandom(1, 6)
            c = nosrandom(1, 6)
            
            if a == 1 and b == 1 and c == 1:
                return f"出目は 『{a}』『{b}』『{c}』\nピンゾロだったよ！"
            elif a == b and b == c:
                return f"出目は『{a}』『{b}』『{c}』\nゾロ目だよ"
            elif a == 4 and b == 5 and c == 6:
                return f"出目は『{a}』『{b}』『{c}』\nシゴロだよ、、、"
            else:
                return f"出目は『{a}』『{b}』『{c}』だったよ"
        
        def tell_fortune() -> str:
            results = [
                ("大吉", "最高の一日になりそう！"),
                ("吉", "良いことがありそう。"),
                ("中吉", "穏やかに過ごせます。"),
                ("小吉", "ささやかな幸せがあるかも。"),
                ("末吉", "焦らずマイペースにいきましょう。"),
                ("凶", "無理せず省エネモードで過ごしましょう。")
            ]
            lucky_items = ["コーヒー", "ミントタブレット", "青いペン", "散歩", "好きな音楽", "猫の動画"]
        
            omikuji, comment = random.choice(results)
            item = random.choice(lucky_items)
        
            return f"🔮今日の運勢: 【{omikuji} 】\n{comment}\nラッキーアイテム: {item}"

        def choose_option(text: str) -> str:
            clean_text = re.sub(r"(選んで|どれ|どっち|ルーレット|決めて|choice)", "", text, flags=re.IGNORECASE).strip()
            items = [item.strip() for item in re.split(r"[,、とか\s]+", clean_text) if item.strip()]
            
            if len(items) < 2:
                return "選択肢がなくて決めれないよ、、、"
            
            selected = random.choice(items)
            return f"う～ん、、、『{selected}』かな？、、、"

        def get_nosrandom(text: str) -> str:
            clean_text = re.sub(r"(ランダム|乱数)", "", text, flags=re.IGNORECASE).strip()
            items = [item.strip() for item in re.split(r"[,、\s]+", clean_text) if item.strip()]
            
            if len(items) < 2:
                return "最小値と最大値を決めてね、、、"
            elif len(items) > 2:
                return "最小値と最大値以外はいらないよ、、、"
            
            if int(items[1]) == 0:
                return "最大値が0だと数字が出せないよ、、、"
            
            a = int(items[0])
            b = int(items[1])
            return f"{nosrandom(a, b)} かな？、、、"

        # -------------------------------------------------------------
        # マッチした場合の判定・返信処理
        # -------------------------------------------------------------
        should_zap = check_praise_and_zap_trigger(cmd, probability=0.0001)
        reply_text = ""
        is_saying_goodnight = False
        
        # 後ろに本文がない場合
        if not cmd:
            resp = [
                "よんだ？、、、",
                "やみ、、、だよ？",
                "呼ばれた気がする、、、",
                "にゃん///" if nosrandom(1, 1000) == 1 else "なに、かな？",
            ]
            reply_text = random.choice(resp)                
        else:
            replies = []

            if any(k in cmd for k in ["サイコロ", "ダイス", "dice"]):
                replies.append(roll_dice())
                
            if "確サイ" in cmd:
                replies.append(f"サイコロを振ったよ、、、{nosrandom(1,6)}だったよ")
            
            if any(k in cmd for k in ["チンチロ", "ちんちろ"]):
                replies.append(chinchiro())
            
            if any(k in cmd for k in ["ランダム", "乱数"]):
                replies.append(get_nosrandom(cmd))
            
            if any(k in cmd for k in ["占い", "おみくじ", "運勢"]):
                replies.append(tell_fortune())
            
            if any(k in cmd.lower() for k in PRAISE_KEYWORDS):
                replies.append("、、、ありがとう")
                
            if any(k in cmd for k in ["選んで", "どっち", "どれ", "ルーレット"]):
                replies.append(choose_option(cmd))
                
            if "おはよう" in cmd:
                resp = [
                    "おはよう",
                    "今日もいい一日でありますように",
                    "よく眠れた？",
                    "今日も、、よろしくね",
                    "もう起きてたよ。待ってた",
                ]
                replies.append(random.choice(resp))
            
            if "こんにちは" in cmd:
                resp =[
                    "こんにちは",
                    "うん、こんにちは",
                    "待ってた、、よ？",
                    "こんにちは、、、今日は何をしていたのかな？"
                ]
                replies.append(random.choice(resp))
            
            if "こんばんは" in cmd:
                resp = [
                    "こんばんは",
                    "1日お疲れ様",
                    "こんばんは\nまだ起きているの？" if (0 <= datetime.now.hour <= 4) else "こんばんは\n夜は静かでいいね、、、",
                ]
                replies.append(random.choice(resp))
            
            if "おやすみ" in cmd:
                resp = [
                    "おやすみ、、、",
                    "また明日ね",
                ]
                replies.append(random.choice(resp))
                if self.target_hex_pubkey and author_hex == self.target_hex_pubkey:
                    is_saying_goodnight = True
            
            if "疲れた" in cmd:
                resp = [
                    "お疲れ様、、、",
                    "ゆっくり休んで、、ね、、、",
                    "無理しないでね",
                    "お茶、入れてくる",
                ]
                replies.append(random.choice(resp))
            
            if any(k in cmd for k in ["きょもなん", "今日もなんとか"]):
                resp = [
                    "今日もなんとかがんばろうね",
                    "今日もなんとか、、、",
                    "今日もなんとか、、、乗り切ろう",
                    "今日もなんとか生き残ろうね",
                ]
                replies.append(random.choice(resp))
            
            if any(k in cmd for k in ["ごごなん", "午後なん", "午後もなんとか"]):
                resp = [
                    "午後もなんとかがんばろうね",
                    "午後もなんとか、、、",
                    "午後もなんとか乗り切ろう",
                    "午後もなんとか生き残ろうね",
                ]
                replies.append(random.choice(resp))
            
            if "しても" in cmd or "でも" in cmd and "いい？" in cmd:
                resp = [
                    "いいと思う、、、よ？",
                    "絶対、、、だめ",
                ]
                replies.append(random.choice(resp))
            
            if "自己紹介" in cmd:
                replies.append("やみです、、、\nあまり役に立てないと思うけど\nよろしくお願いします、、、")
            
            if "できること" in cmd:
                replies.append("[ダイス]と言われたらサイコロを振るし\n[占い]と言われたら占うし\n選択肢をくれたら代わりに決めてあげられるよ")
            
            if replies:
                reply_text = "\n".join(replies)
            else:
                resp = [
                    "ごめん難しくてよくわからないや、、、",
                    "なんかサイコロのランダムは\nNostrの投稿を\nノイズにしてるんだって\nよくわからないや、、、",
                    "難しいな、、、\n[できること]と聞いてくれたらやみのできることを教えてあげる、、よ？",
                ]
                
                reply_text = random.choice(resp)

        trigger_type = "メンション" if is_mentioned else "キーワード"
        print(f"[{trigger_type}] 抽出された命令: '{cmd}' (区切り: '{delimiter}')")

        builder = EventBuilder.text_note_reply(reply_text, event)
        await self.client.send_event_builder(builder)
        
        if should_zap:
            asyncio.create_task(send_zap_via_nwc(event, sats=21))
            
        if is_saying_goodnight:
            self.is_bot_active = False
            print("やみを停止しました")

    async def handle_msg(self, relay_url, msg):
        # 生メッセージの処理が必要ない場合はパスでOK
        pass

async def main():
    keys = Keys.parse(nsec)
    signer = NostrSigner.keys(keys)
    client = Client(signer)

    # リレーの追加
    await client.add_relay(RelayUrl.parse("wss://relay.yoinekodo.jp"))
    await client.add_relay(RelayUrl.parse("wss://yabu.me"))
    await client.connect()

    # フィルター設定
    f = Filter().kind(Kind(1)).limit(0)
    await client.subscribe(f, None)

    print(f"やみ起床中... (npub: {keys.public_key().to_bech32()})")

    # ハンドラーのインスタンス化して渡す
    handler = MyNotificationHandler(client, keys.public_key())
    
    try:
        await client.handle_notifications(handler)
    finally:
        await client.disconnect()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("やみ睡眠中...")