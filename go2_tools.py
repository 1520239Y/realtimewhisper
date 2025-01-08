import time
from unitree_sdk2py.core.channel import ChannelSubscriber, ChannelFactoryInitialize
from unitree_sdk2py.go2.sport.sport_client import SportClient

ChannelFactoryInitialize(0, "enp0s8")
client = SportClient()
client.SetTimeout(10.0)
client.Init()
dt = 0.01
    
def StandUp():
    client.RiseSit()
    time.sleep(1)

def SitDown():
    client.Sit()
    time.sleep(1)

def Stretch():
    client.Stretch()
    time.sleep(1)

def Dance():
    client.Dance1()
    time.sleep(1)

def FrontJump():
    client.FrontJump()
    time.sleep(1)

def Heart():
    client.Heart()
    time.sleep(1)

def FrontFlip():
    client.FrontFlip()
    time.sleep(1)

def Move(x, y, z):
    """x(m)、y(m)、z(rad)回転する"""
    for i in range(int(x / dt)):
        client.Move(1, 0, 0)
        time.sleep(dt)
    client.StopMove()

    for i in range(int(y / dt)):
        client.Move(0, 1, 0)
        time.sleep(dt)
    client.StopMove()

    for i in range(int(z / dt)):
        client.Move(0, 0, 1)
        time.sleep(dt)
    client.StopMove()

    time.sleep(1)

def FrontPounce():
    """威嚇する"""
    client.FrontPounce()
    time.sleep(1)

def Hello():
    """挨拶する"""
    client.Hello()
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
