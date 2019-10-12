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
import settings
import os

url = 'https://passport.weibo.cn/signin/login'
start_url = 'https://weibo.cn/{}?filter=1'.format(settings.WEIBO_ID)
'''设置并发数'''
sema = asyncio.Semaphore(2)

headers = {'User-Agent': 'Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/75.0.3770.90 Mobile Safari/537.36'}


async def get_cookies():
    '''启动puppeteer模拟登录微博'''
    browser = await launch(args=['--no-sandbox'])
    page = await browser.newPage()
    try:
        await page.goto(url)
        await page.waitFor(2000)
        await page.type('#loginName', settings.USERNAME)
        await page.type('#loginPassword', settings.PASSWORD)
        await page.keyboard.press('Enter')
        await page.waitFor(3000)
        await page.goto(start_url)
        cookies = await page.cookies()
        page_count = await page.xpath('//input[@name="mp"]')
        page_count = await page_count[0].getProperty('value')
        page_count = await page_count.jsonValue()
        print('总共有{}页需要爬取'.format(page_count))
        await browser.close()
        new_cookies = {}
        for c in cookies:
            new_cookies[c['name']] = c['value']
        print('获取登录状态成功')
        return new_cookies, page_count
    except Exception as e:
        print('获取登录状态失败')
        print(e)


async def download(session, url, cookies):
    '''下载页面'''
    async with session.get(url=url, headers=headers, cookies=cookies) as response:
        response = await response.text()
        '''暂停5秒避免反爬'''
        await asyncio.sleep(5)
        return response.encode('utf-8')


async def parse(session, cookies, html, loop):
    '''解析出所有的图片URL并进行下载'''
    response = etree.HTML(html)
    title_imgs = response.xpath('//div[@class="c"]')
    for img in title_imgs:
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
            loop.create_task(download_img(session, single_img_url))
        elif multi_img_url:
            multi_img_url = [img.split('/')[-1] for img in multi_img_url]
            [loop.create_task(download_img(session, img_url)) for img_url in multi_img_url]
    await asyncio.sleep(5)


async def download_img(session, img_url):
    '''下载图片'''
    img_url = 'http://ww2.sinaimg.cn/large/' + img_url
    try:
        async with session.get(url=img_url, headers=headers) as response:
            assert response.status == 200
            with open('{}'.format('images/{}/'.format(settings.WEIBO_ID) + img_url.split('/')[-1].strip('.jpg') + '.jpg'), 'wb') as w:
                while 1:
                    img_resp = await response.content.read()
                    if not img_resp:
                        break
                    w.write(img_resp)
            print('download {} end'.format(img_url))
            await asyncio.sleep(5)
    except Exception as e:
        print('下载图片错误{}'.format(img_url))
        print(e)


async def start(url, cookies, loop):
    async with sema:
        async with aiohttp.ClientSession() as session:
            html = await download(session, url, cookies)
            await parse(session, cookies, html, loop)
            await asyncio.sleep(5)


if '__main__' == __name__:
    if os.path.exists('images/{}'.format(settings.WEIBO_ID)):
        print('ID目录存在')
        pass
    else:
        print('ID目录不存在')
        os.mkdir('images/{}'.format(settings.WEIBO_ID))
        print('创建ID目录成功')

    loop = asyncio.get_event_loop()
    cookies, page_count = loop.run_until_complete(get_cookies())
    if cookies and page_count:
        '''获取总页数后生成每一页的URL添加到任务里'''
        tasks = [asyncio.ensure_future(start(start_url + '&page={}'.format(page), cookies, loop)) for page in range(1, int(page_count) + 1)]
        tasks = asyncio.gather(*tasks)
        loop.run_until_complete(tasks)
