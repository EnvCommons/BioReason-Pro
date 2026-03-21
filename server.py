from openreward.environments import Server

from bioreason_pro import BioReasonPro

if __name__ == "__main__":
    server = Server([BioReasonPro])
    server.run()
