import requests
import json
import hashlib
import random
import time
from urllib.parse import quote
import urllib.request
import urllib.parse

class OnlineTranslator:
    """在线翻译引擎管理类"""
    
    def __init__(self):
        self.translators = {
            'google': GoogleTranslator(),
            'deepl': DeepLTranslator(),
            'baidu': BaiduTranslator(),
            'microsoft': MicrosoftTranslator()
        }
        self.current_translator = 'google'  # 默认使用Google翻译
        
    def set_translator(self, translator_name):
        """设置当前翻译引擎"""
        if translator_name in self.translators:
            self.current_translator = translator_name
            return True
        return False
    
    def get_available_translators(self):
        """获取可用的翻译引擎列表"""
        return list(self.translators.keys())
    
    def translate(self, text, from_lang, to_lang):
        """翻译文本"""
        if not text or not text.strip():
            return ""
        
        translator = self.translators[self.current_translator]
        try:
            return translator.translate(text, from_lang, to_lang)
        except Exception as e:
            print(f"翻译失败 ({self.current_translator}): {e}")
            # 如果当前翻译器失败，尝试备用翻译器
            for name, backup_translator in self.translators.items():
                if name != self.current_translator:
                    try:
                        print(f"尝试备用翻译器: {name}")
                        return backup_translator.translate(text, from_lang, to_lang)
                    except:
                        continue
            raise Exception(f"所有翻译引擎都失败了: {e}")


class GoogleTranslator:
    """Google翻译 - 免费版本"""
    
    def __init__(self):
        self.base_url = "https://translate.googleapis.com/translate_a/single"
        # 语言代码映射
        self.lang_map = {
            'zh': 'zh-cn',
            'ja': 'ja',
            'en': 'en',
            'ko': 'ko',
            'ms': 'ms'
        }
    
    def translate(self, text, from_lang, to_lang):
        """使用Google翻译API翻译文本"""
        # 映射语言代码
        from_lang = self.lang_map.get(from_lang, from_lang)
        to_lang = self.lang_map.get(to_lang, to_lang)
        
        params = {
            'client': 'gtx',
            'sl': from_lang,
            'tl': to_lang,
            'dt': 't',
            'q': text
        }
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        try:
            response = requests.get(self.base_url, params=params, headers=headers, timeout=10)
            response.raise_for_status()
            
            # 解析响应
            result = response.json()
            if result and result[0]:
                translated_text = ''.join([item[0] for item in result[0] if item[0]])
                return translated_text.strip()
            
        except Exception as e:
            raise Exception(f"Google翻译失败: {e}")
        
        return text


class DeepLTranslator:
    """DeepL翻译 - 免费版本"""
    
    def __init__(self):
        self.base_url = "https://api-free.deepl.com/v2/translate"
        # 注意：需要API密钥，这里提供免费版本的实现
        self.api_key = None  # 用户需要设置API密钥
        
        # 语言代码映射
        self.lang_map = {
            'zh': 'ZH',
            'ja': 'JA',
            'en': 'EN',
            'ko': 'KO',
            'ms': 'MS'  # DeepL可能不支持马来语
        }
    
    def set_api_key(self, api_key):
        """设置DeepL API密钥"""
        self.api_key = api_key
    
    def translate(self, text, from_lang, to_lang):
        """使用DeepL API翻译文本"""
        if not self.api_key:
            # 尝试使用免费的DeepL网页版（不稳定）
            return self._translate_web_version(text, from_lang, to_lang)
        
        # 映射语言代码
        from_lang = self.lang_map.get(from_lang, from_lang.upper())
        to_lang = self.lang_map.get(to_lang, to_lang.upper())
        
        headers = {
            'Authorization': f'DeepL-Auth-Key {self.api_key}',
            'Content-Type': 'application/json'
        }
        
        data = {
            'text': [text],
            'source_lang': from_lang,
            'target_lang': to_lang
        }
        
        try:
            response = requests.post(self.base_url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result.get('translations'):
                return result['translations'][0]['text']
                
        except Exception as e:
            raise Exception(f"DeepL翻译失败: {e}")
        
        return text
    
    def _translate_web_version(self, text, from_lang, to_lang):
        """使用DeepL网页版进行翻译（备用方案）"""
        # 这是一个简化的实现，实际可能需要更复杂的处理
        try:
            # 构造请求URL
            url = "https://www2.deepl.com/jsonrpc"
            
            # 简化的请求数据
            data = {
                "jsonrpc": "2.0",
                "method": "LMT_handle_jobs",
                "params": {
                    "jobs": [{
                        "kind": "default",
                        "raw_en_sentence": text,
                        "raw_en_context_before": [],
                        "raw_en_context_after": [],
                        "preferred_num_beams": 1
                    }],
                    "lang": {
                        "source_lang_user_selected": from_lang.upper(),
                        "target_lang": to_lang.upper()
                    },
                    "priority": 1,
                    "commonJobParams": {},
                    "timestamp": int(time.time() * 1000)
                },
                "id": random.randint(1, 99999999)
            }
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=15)
            if response.status_code == 200:
                result = response.json()
                if 'result' in result and 'translations' in result['result']:
                    translations = result['result']['translations']
                    if translations and 'beams' in translations[0]:
                        return translations[0]['beams'][0]['postprocessed_sentence']
            
        except Exception as e:
            print(f"DeepL网页版翻译失败: {e}")
        
        # 如果失败，返回原文
        return text


class BaiduTranslator:
    """百度翻译"""
    
    def __init__(self):
        self.base_url = "https://fanyi-api.baidu.com/api/trans/vip/translate"
        # 注意：需要APP ID和密钥
        self.app_id = None
        self.secret_key = None
        
        # 语言代码映射
        self.lang_map = {
            'zh': 'zh',
            'ja': 'jp',
            'en': 'en',
            'ko': 'kor',
            'ms': 'may'
        }
    
    def set_credentials(self, app_id, secret_key):
        """设置百度翻译API凭据"""
        self.app_id = app_id
        self.secret_key = secret_key
    
    def translate(self, text, from_lang, to_lang):
        """使用百度翻译API翻译文本"""
        if not self.app_id or not self.secret_key:
            # 尝试使用免费的百度翻译网页版
            return self._translate_web_version(text, from_lang, to_lang)
        
        # 映射语言代码
        from_lang = self.lang_map.get(from_lang, from_lang)
        to_lang = self.lang_map.get(to_lang, to_lang)
        
        # 生成签名
        salt = str(random.randint(32768, 65536))
        sign_str = self.app_id + text + salt + self.secret_key
        sign = hashlib.md5(sign_str.encode()).hexdigest()
        
        params = {
            'q': text,
            'from': from_lang,
            'to': to_lang,
            'appid': self.app_id,
            'salt': salt,
            'sign': sign
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if 'trans_result' in result:
                return result['trans_result'][0]['dst']
            elif 'error_code' in result:
                raise Exception(f"百度翻译API错误: {result.get('error_msg', result['error_code'])}")
                
        except Exception as e:
            raise Exception(f"百度翻译失败: {e}")
        
        return text
    
    def _translate_web_version(self, text, from_lang, to_lang):
        """使用百度翻译网页版（简化版本）"""
        try:
            # 这是一个非常基础的实现
            url = "https://fanyi.baidu.com/sug"
            data = {'kw': text}
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.post(url, data=data, headers=headers, timeout=10)
            if response.status_code == 200:
                result = response.json()
                if result.get('data'):
                    return result['data'][0]['v']
            
        except Exception as e:
            print(f"百度网页版翻译失败: {e}")
        
        return text


class MicrosoftTranslator:
    """微软翻译"""
    
    def __init__(self):
        self.base_url = "https://api.cognitive.microsofttranslator.com/translate"
        self.api_key = None
        self.region = "global"
        
        # 语言代码映射
        self.lang_map = {
            'zh': 'zh-Hans',
            'ja': 'ja',
            'en': 'en',
            'ko': 'ko',
            'ms': 'ms'
        }
    
    def set_credentials(self, api_key, region="global"):
        """设置微软翻译API凭据"""
        self.api_key = api_key
        self.region = region
    
    def translate(self, text, from_lang, to_lang):
        """使用微软翻译API翻译文本"""
        if not self.api_key:
            # 尝试使用免费的微软翻译网页版
            return self._translate_web_version(text, from_lang, to_lang)
        
        # 映射语言代码
        from_lang = self.lang_map.get(from_lang, from_lang)
        to_lang = self.lang_map.get(to_lang, to_lang)
        
        headers = {
            'Ocp-Apim-Subscription-Key': self.api_key,
            'Ocp-Apim-Subscription-Region': self.region,
            'Content-Type': 'application/json'
        }
        
        params = {
            'api-version': '3.0',
            'from': from_lang,
            'to': to_lang
        }
        
        body = [{'text': text}]
        
        try:
            response = requests.post(self.base_url, params=params, headers=headers, json=body, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            if result and result[0].get('translations'):
                return result[0]['translations'][0]['text']
                
        except Exception as e:
            raise Exception(f"微软翻译失败: {e}")
        
        return text
    
    def _translate_web_version(self, text, from_lang, to_lang):
        """使用微软翻译网页版（备用方案）"""
        # 简化实现，实际情况可能需要更复杂的处理
        return text


# 使用示例
if __name__ == "__main__":
    # 创建在线翻译器
    online_translator = OnlineTranslator()
    
    # 测试文本
    test_text = "Hello, world!"
    
    # 测试不同的翻译引擎
    for translator_name in online_translator.get_available_translators():
        online_translator.set_translator(translator_name)
        try:
            result = online_translator.translate(test_text, 'en', 'zh')
            print(f"{translator_name}: {result}")
        except Exception as e:
            print(f"{translator_name}: 失败 - {e}")