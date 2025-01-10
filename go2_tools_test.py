import time
    
def StandUp():
    print("StandUp")
    time.sleep(1)

def SitDown():
    print("SitDown")
    time.sleep(1)

def Stretch():
    print("Stretch")
    time.sleep(1)

def Dance():
    print("Dance")
    time.sleep(1)

def FrontJump():
    print("FrontJump")
    time.sleep(1)

def Heart():
    print("Heart")
    time.sleep(1)

def FrontFlip():
    print("FrontFlip")
    time.sleep(1)

def FrontPounce():
    print("FrontPounce")
    time.sleep(1)

def Hello():
    print("Hello")
    time.sleep(1)

tool_dict = {
    "StandUp": StandUp,
    "SitDown": SitDown,
    "Stretch": Stretch,
    "Dance": Dance,
    "Heart": Heart,
    "FrontFlip": FrontFlip,
    "FrontPounce": FrontPounce,
    "Hello": Hello
}

tools = [
    {"type": "function", "name": "StandUp", "description": "立ち上がる"},
    {"type": "function", "name": "SitDown", "description": "座る"},
    {"type": "function", "name": "Stretch", "description": "ストレッチする"},
    {"type": "function", "name": "Dance", "description": "ダンスする"},
    {"type": "function", "name": "Heart", "description": "ハートを描く"},
    {"type": "function", "name": "FrontFlip", "description": "バク転する"},
    {"type": "function", "name": "FrontPounce", "description": "威嚇する"},
    {"type": "function", "name": "Hello", "description": "挨拶する"}
]