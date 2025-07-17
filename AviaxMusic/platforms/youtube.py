



import aiohttp
import config
import io
import uuid


from pyrogram import filters, types
from nandha import pbot


__module__ = "Youtube"
__help__ = """
*Commands*:
/yt, /ytsong, /ytvideo

```
/yt <url>:
get direct download link of youtube video / audio.
/ytsong <url>: downloader for yt song by url.
/ytvideo <url>: downloader for yt video by url.
```

*Example*:
`/yt https://youtube.com/shorts/RSn4Cl-trS8?si=_oQSz9md-_abLJve`
`/ytsong url`
`/ytvideo url`
"""

temp_data = {}


@pbot.on_message(filters.command('yt') & ~filters.forwarded)
async def youtube_cmd(_, message):
       m = message
       user = m.from_user
       link = m.text.split()[1] if len(m.text.split()) > 1 else None

       if not link: return await m.reply('/yt url')
       if link[:27] == 'https://youtube.com/shorts/':
           link = link[27:38]
       elif link[:17] == 'https://youtu.be/':
           link = link[17:28]
       else:
            return m.reply("**This url seems not supported please report to /support.**")

       msg = await m.reply_text('📩** Trying to downloading ...**')
  
       url = "https://youtube-media-downloader.p.rapidapi.com/v2/video/details"
       query = {"videoId": link}
  
       headers = {
        "X-RapidAPI-Key": "3d579d87b6msh8e40272f2bd1036p1b3e47jsnc7a47101736b",
        "X-RapidAPI-Host": "youtube-media-downloader.p.rapidapi.com"
        }
       
       async with aiohttp.ClientSession() as session:
             async with session.get(url, headers=headers, params=query) as response:
                  try:
                     data = await response.json()
                     if data.get('status'):
                            
                         id = data['id']
                         title = data['title']
                         description = data.get('description', 'N/A')[0:500]
                         likeCount = str(data.get('likeCount', 'N/A')) + " 👍"
                         viewCount = str(data.get('viewCount', 404)) + " 👀"
                         seconds = int(data.get('lengthSeconds', 404))
                            
                         duration = f"⏰ {int(seconds/60)} Minutes" if seconds > 59 else f"⏰ {seconds} Seconds"
                         buttons = []
                         row = []
                         photo = data['thumbnails'][-1]['url']
                         datas = data['videos']['items'] + data['audios']['items']
                         for d in datas[:50]:
                             
                             if len(row) == 2:
                                  buttons.append(row)
                                  await m.reply_text(title, reply_markup=types.InlineKeyboardMarkup(buttons))
                                  buttons = []
                                  row = []
                             else:
                                  type = d['mimeType'].split(';')[0]
                                  extension = d['extension']
                                  if extension.lower() == "mp4":
                                       text = f"video:{d['sizeText']}, (Audio:{d['hasAudio']}) (type:{type})"
                                  else:
                                       text = f"Audio:{d['sizeText']}, type:{type}"
                                  row.append(types.InlineKeyboardButton(text, url=d['url']))
                         if row:
                              buttons.append(row)
                              await m.reply_text(title, reply_markup=types.InlineKeyboardMarkup(buttons))
                              row = []
                         
                         
                         text = (
                            f"📛 **Title**: `{title}` — (`{id}`)\n"
                            f"ℹ️ **Description**: `{description}`\n"
                            f"✨ **Likes**: `{likeCount}`\n"
                            f"👤 **Views**: `{viewCount}`\n\n"
                            f"**By {config.BOT_USERNAME}**"
                         )
                         await msg.edit_media(
                                media=types.InputMediaPhoto(photo, caption=text)
                         )
                                              
                         temp_data[user.id] = {
                                'id': id,
                                'photo': photo,
                                'title': title, 
                                'description': description,
                                'viewCount': viewCount,
                                'likeCount': likeCount,
                                'medias': datas,
                              }
                     else:
                         return await msg.edit("❌ Status invalid!")
                         
                  except Exception as e:
                       return await msg.edit(f'❌ ERROR: {str(e)}')








async def yt_search(query: str):
    pass

async def yt_download(url, is_audio=False, is_video=False):
    async with aiohttp.ClientSession() as session:
        api_url = f"https://yt-vid.hazex.workers.dev/?url={url}"
        async with session.get(api_url) as response:  # Changed url to api_url
            results = await response.json()
            if is_audio:
                media_url = results.get('audio', [{}])[0].get('url', None)
                type = "audio"
            else:
     
                media_url = results.get('video_with_audio', [{}])[0].get('url', None)
                type = "video"
             
            if not media_url:
                raise Exception("I can't get media_url for this video.") 
            
            return {
                'error': results['error'],
                'message': results.get('message', '🤨 No errors from api.'),
                'type': type,
                'url': media_url,
                'title': results['title'],
                'thumb_url': results['thumbnail'],
                'duration': results['duration'],
            }

async def get_file(url: str, media_type: str):
    async with aiohttp.ClientSession() as session:
        headers = {
 'X-Forwarded-For': '27.62.106.26',
 'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36',
 'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
 'sec-ch-ua-platform': 'Android',
 'sec-ch-ua': 'Not-A.Brand;v=99;Chromium;v=124'
}
        async with session.get(url, headers=headers) as response:
            if response.status != 200:
                raise ValueError(f"Failed to download file: HTTP {response.status}")
            
            # Read the content in chunks
            data = io.BytesIO()
            chunk_size = 1024 * 1024  # 1MB chunks
            
            async for chunk in response.content.iter_chunked(chunk_size):
                data.write(chunk)
            
            # Important: seek to beginning after writing
            data.seek(0)
            
            # Verify file size
            file_size = data.getbuffer().nbytes
            if file_size == 0:
                raise ValueError("Downloaded file is empty")
            
            # Set appropriate filename
            if media_type == "audio":
                filename = f"yt_audio_{uuid.uuid4()}.mp3"
            else:
                filename = f"yt_video_{uuid.uuid4()}.mp4"
            
            data.name = filename
            return data


@pbot.on_message(filters.command(['ytsong', 'ytvideo']) & ~filters.forwarded)
async def youtube_dl(_, message):
    m = message

    if len(m.text.split()) < 2:
        return await m.reply_text('**Provide me YouTube url** ✋')
        
    cmd = m.command[0].lower()
    is_audio, is_video = (True, False) if cmd == "ytsong" else (False, True)
    
    q_url, query = m.text.split()[1], m.text.split(maxsplit=1)[1]
    
    msg = await m.reply('🔄 **Processing downloading...**')
    
    if q_url.startswith('https://'):
        ytdl_result = await yt_download(q_url, is_audio=is_audio, is_video=is_video)
    else:
        return await msg.edit('**Currently search by query not available at the moment** ( :')
        # yt_url = await yt_search(query)  # Commented out since yt_search is not implemented
        # ytdl_result = await yt_download(yt_url)
    
    if ytdl_result['error']:
        return await msg.edit(f'**❌ Error when downloading**: {ytdl_result["message"]}')  # Fixed string formatting
        
    media_type = ytdl_result['type']
    dl_url = ytdl_result['url']
    
    text = f"**{ytdl_result['title']}\n\n❤️ by {config.BOT_USERNAME}**"  # Added f-string
    await m.reply_photo(ytdl_result['thumb_url'], caption=text)
    
    try:
        file = await get_file(dl_url, media_type)
    except Exception as e:
        return await msg.edit(f'**❌ Error when saving file**: {e}')
    
    method = m.reply_audio if media_type == 'audio' else m.reply_video
    await method(
        file, 
        duration=ytdl_result['duration'],  # Fixed variable name from yt_result to ytdl_result
        caption=f"**❤️ By {config.BOT_USERNAME}**"  # Added f-string
    )
    await msg.delete()
                  
       
       
