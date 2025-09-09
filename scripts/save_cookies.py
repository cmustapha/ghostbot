from selenium import webdriver
import json

url = "https://www.tumblr.com/login"
driver = webdriver.Chrome()
driver.get(url)
input("✅ Connecte-toi puis appuie sur Entrée...")
cookies = driver.get_cookies()
with open("cookies/tumblr_ghost01.json", "w") as f:
    json.dump(cookies, f)
print("✅ Cookies sauvegardés.")
driver.quit()
