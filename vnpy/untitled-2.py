from socket import *
from multiprocessing import Process
s=socket(AF_INET,SOCK_STREAM)
s.setsockopt(SOL_SOCKET,SO_REUSEADDR,1) #就是它，在bind前加
s.bind(('127.0.0.1',8088))
s.listen(5)
def talk(conn,addr):
    while True: #通信循环
        try:
            data=conn.recv(1024)
            if not data:break
            conn.send(data.upper())
        except Exception:
            break
    conn.close()
if __name__ == '__main__':
    while True:#链接循环
        conn,addr=s.accept()
        p=Process(target=talk,args=(conn,addr))
        p.start()
    s.close()