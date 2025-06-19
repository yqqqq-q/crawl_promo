from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# Setup headless browser
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(options=options)

# Go to the initial redirect link
driver.get("https://go.dealmoon.com/exec/j?d=5036138")

# Wait for redirect to complete
driver.implicitly_wait(5)

# Get final URL
final_url = driver.current_url
print("Final URL:", final_url)

driver.quit()