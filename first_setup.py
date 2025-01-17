import CAT24C256
from DatabaseManager import DatabaseManager as db

eeprom = CAT24C256.EEPROMManager(0x50, 256, 1, 19, 18)

def pad_data(data: str, length: int) -> str:
    data_bytes = data.encode('utf-8')
    if len(data_bytes) >= length:
        return data
    padded_data = data_bytes + b' ' * (length - len(data_bytes))
    print(f"Padded Data: {padded_data}")
    return padded_data.decode('latin-1')

eeprom.wipe_all()
db=db()
db.read_general_info()
def_pass = "123456"
db.save_admin_pswd(pad_data(def_pass, 16), True)
for i in range(10):
    print(f"Pagina {i}: {eeprom.read(i,1)}")