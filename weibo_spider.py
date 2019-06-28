######################################################
# -*- coding:utf-8 -*-
# !/usr/bin/python
# > File Name: test.py
# > #Author: Junjie.Lu
# > Created Time: 2019年06月27日 星期四 16时20分52秒
######################################################
from pyppeteer import launch
import asyncio
from lxml import etree
import aiohttp
from .settings import USERNAME, PASSWORD, WEIBO_ID

url = 'https://passport.weibo.cn/signin/login'

start_url = 'https://weibo.cn/{}?filter=1'.format(WEIBO_ID)

sema = asyncio.Semaphore(3)


async def get_cookies():
    browser = await launch(args=['--no-sandbox'])
    page = await browser.newPage()
    await page.goto(url)
    await page.waitFor(2000)
    await page.type('#loginName', USERNAME)
    await page.type('#loginPassword', PASSWORD)
    await page.keyboard.press('Enter')
    await page.waitFor(3000)
    await page.goto(start_url)
    cookies = await page.cookies()
    page_count = await page.xpath('//input[@name="mp"]')
    page_count = await page_count[0].getProperty('value')
    page_count = await page_count.jsonValue()
    print('total page {}'.format(page_count))
    await browser.close()
    new_cookies = {}
    for c in cookies:
        new_cookies[c['name']] = c['value']
    print('get cookies')
    return new_cookies, page_count


async def download(session, url, cookies):
    async with session.get(url=url, cookies=cookies) as response:
        response = await response.text()
        return response.encode('utf-8')


async def parse(session, cookies, html, loop):
    if not html:
        return []
    response = etree.HTML(html)
    title = response.xpath('//div[@class="c"]')
    for img in title:
        title = img.xpath('.//span[@class="ctt"]/text()')
        imgs = img.xpath('.//a[contains(text(), "组图")]')
        single_img_url = img.xpath('.//div[2]//a[contains(text(),"原图")]/@href')
        multi_img_url = img.xpath('.//img[contains(@alt, "图片加载")]/@src')

        if imgs:
            imgs_url = imgs[0].xpath('./@href')
            for img_url in imgs_url:
                async with session.get(url=img_url, cookies=cookies) as resp:
                    imgs_text = await resp.text()
                    await parse(session, cookies, imgs_text.encode('utf-8'), loop)
            continue
        elif single_img_url:
            single_img_url = single_img_url[0].split('=')[-1]
            asyncio.ensure_future(download_img(session, single_img_url))
        elif multi_img_url:
            multi_img_url = [img.split('/')[-1] for img in multi_img_url]
            [asyncio.ensure_future(download_img(session, img_url)) for img_url in multi_img_url]


async def download_img(session, img_url):
    img_url = 'http://ww2.sinaimg.cn/large/' + img_url
    print(img_url)
    try:
        async with session.get(url=img_url) as response:
            with open('{}'.format('images/' + img_url.split('/')[-1]), 'wb') as w:
                assert response.status == 200
                while 1:
                    img_resp = await response.content.read()
                    if not img_resp:
                        break
                    w.write(img_resp)
    except Exception as e:
        print(e)


async def start(url, cookies, loop):
    async with sema:
        async with aiohttp.ClientSession() as session:
            html = await download(session, url, cookies)
            await parse(session, cookies, html, loop)
            await asyncio.sleep(5)


if '__main__' == __name__:
    loop = asyncio.get_event_loop()
    cookies, page_count = loop.run_until_complete(get_cookies())
    tasks = [asyncio.ensure_future(start(start_url + '&page={}'.format(page), cookies, loop)) for page in range(1, int(page_count) + 1)]
    tasks = asyncio.gather(*tasks)
    loop.run_until_complete(tasks)
