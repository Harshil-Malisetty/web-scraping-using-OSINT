
import tweepy
import pandas as pd
import os
import json
from datetime import datetime
import requests
import re

OUTPUT_DIR = "osint_results"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TWITTER_BEARER_TOKEN = "AAAAAAAAAAAAAAAAAAAAAAz0zgEAAAAAishvMyETOkBNUsiO8XzNPckkpPc%3DTBFqc6hv3HXS81DFh2cwa4Q7Yoi9JbRadPiACVx2kZwDjj42tb"

GOOGLE_API_KEY = "AIzaSyBILdCEDwh8V8kTRNWUVOxzTB3bWQR8lQA"
SEARCH_ENGINE_ID = "7631513633bb24d3d"

try:
    twitter_client = tweepy.Client(bearer_token=TWITTER_BEARER_TOKEN)
    print("✅ Twitter API client initialized")
except Exception as e:
    print(f"❌ Failed to initialize Twitter API client: {e}")
    twitter_client = None

SOCIAL_MEDIA_SITES = [
    {
        "name": "LinkedIn",
        "site": "site:linkedin.com/in/",
        "username_pattern": r"linkedin\.com/in/([^/]+)",
        "profile_type": "professional"
    },
    {
        "name": "Twitter",
        "site": "site:twitter.com/",
        "username_pattern": r"twitter\.com/([^/\?]+)(?:/|$|\?)",
        "exclude": "-site:twitter.com/home -site:twitter.com/search -site:twitter.com/explore",
        "profile_type": "social"
    },
    {
        "name": "Facebook",
        "site": "site:facebook.com/",
        "username_pattern": r"facebook\.com/([^/\?]+)(?:/|$|\?)",
        "exclude": "-site:facebook.com/pages -site:facebook.com/groups",
        "profile_type": "social"
    },
    {
        "name": "Instagram",
        "site": "site:instagram.com/",
        "username_pattern": r"instagram\.com/([^/\?]+)(?:/|$|\?)",
        "exclude": "-site:instagram.com/p/ -site:instagram.com/explore",
        "profile_type": "social"
    },
    {
        "name": "GitHub",
        "site": "site:github.com/",
        "username_pattern": r"github\.com/([^/\?]+)(?:/|$|\?)",
        "exclude": "-site:github.com/orgs -site:github.com/topics",
        "profile_type": "development"
    },
    {
        "name": "Reddit",
        "site": "site:reddit.com/user/",
        "username_pattern": r"reddit\.com/user/([^/\?]+)",
        "profile_type": "forum"
    }
]

def get_twitter_user_info(username):
    if not twitter_client:
        print("❌ Twitter API client not available")
        return None
        
    try:
        user = twitter_client.get_user(
            username=username, 
            user_fields=["created_at", "description", "location", "profile_image_url", 
                        "public_metrics", "url", "verified"]
        )
        
        if user.data:
            return {
                "username": user.data.username,
                "user_id": user.data.id,
                "account_created": user.data.created_at,
                "description": user.data.description,
                "location": user.data.location,
                "profile_url": user.data.profile_image_url,
                "website": user.data.url,
                "verified": user.data.verified,
                "followers_count": user.data.public_metrics["followers_count"],
                "following_count": user.data.public_metrics["following_count"],
                "tweet_count": user.data.public_metrics["tweet_count"],
                "listed_count": user.data.public_metrics["listed_count"]
            }
        else:
            print("User not found.")
            return None
    except Exception as e:
        print(f"❌ Error fetching user info: {e}")
        return None

def search_tweets(query, max_tweets=50):
    if not twitter_client:
        print("❌ Twitter API client not available")
        return []
        
    try:
        tweet_fields = ["created_at", "public_metrics"]
        expansions = ["author_id"]
        user_fields = ["username"]
        
        tweets = twitter_client.search_recent_tweets(
            query=query, 
            max_results=max_tweets,
            tweet_fields=tweet_fields,
            expansions=expansions,
            user_fields=user_fields
        )
        
        if not tweets.data:
            print("No tweets found matching the query.")
            return []
        
        data = []
        users_dict = {}
        
        if hasattr(tweets, 'includes') and 'users' in tweets.includes:
            for user in tweets.includes['users']:
                users_dict[user.id] = user
        
        for tweet in tweets.data:
            tweet_data = {
                "tweet_id": tweet.id,
                "text": tweet.text,
                "created_at": tweet.created_at
            }
            
            if hasattr(tweet, 'public_metrics'):
                tweet_data.update({
                    "retweet_count": tweet.public_metrics.get("retweet_count"),
                    "reply_count": tweet.public_metrics.get("reply_count"),
                    "like_count": tweet.public_metrics.get("like_count")
                })
            
            if hasattr(tweet, 'author_id') and tweet.author_id in users_dict:
                tweet_data["author_username"] = users_dict[tweet.author_id].username
            
            data.append(tweet_data)
            
        return data
    
    except Exception as e:
        print(f"❌ Error fetching tweets: {e}")
        return []

def google_search(query, num_results=10):
    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "q": query,
        "key": GOOGLE_API_KEY,
        "cx": SEARCH_ENGINE_ID,
        "num": num_results
    }
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        return data.get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"❌ Error fetching search results: {e}")
        return []

def extract_username(url, pattern):
    match = re.search(pattern, url, re.IGNORECASE)
    if match:
        username = match.group(1)
        username = username.strip().lower()
        username = username.split('?')[0].split('#')[0]
        return username
    return None

def score_profile_relevance(result, target_name):
    score = 0
    
    name_parts = target_name.lower().split()
    
    title = result.get('title', '').lower()
    snippet = result.get('snippet', '').lower()
    content = title + " " + snippet
    
    if target_name.lower() in content:
        score += 3
    
    name_part_matches = 0
    for part in name_parts:
        if len(part) >= 3 and part in content:
            name_part_matches += 1
            
    if name_part_matches > 0:
        score += name_part_matches
    
    username = extract_username(result.get('link', ''), r'/([^/]+)/?$')
    if username:
        username_parts = re.split(r'[._-]', username.lower())
        for name_part in name_parts:
            if len(name_part) >= 3:
                for username_part in username_parts:
                    if len(username_part) >= 3 and (name_part in username_part or username_part in name_part):
                        score += 1
                        break
    
    if any(term in title for term in ['profile', ' - ', '|', 'on']):
        score += 1
    
    if '/profile/' in result.get('link', '').lower():
        score += 1
        
    return score

def is_name_related(result, target_name):
    name_parts = [part.lower() for part in target_name.split() if len(part) >= 3]
    
    title = result.get('title', '').lower()
    snippet = result.get('snippet', '').lower()
    content = title + " " + snippet
    
    for part in name_parts:
        if part in content:
            return True
            
    username = extract_username(result.get('link', ''), r'/([^/]+)/?$')
    if username:
        username_parts = re.split(r'[._-]', username.lower())
        for name_part in name_parts:
            for username_part in username_parts:
                if len(username_part) >= 3 and (name_part in username_part or username_part in name_part):
                    return True
                    
    return False

def social_media_lookup(target_name):
    all_results = []
    
    print(f"\n🔍 Searching social media profiles for: {target_name}")
    
    name_variations = [
        target_name,
        f'"{target_name}"',
        ' '.join(target_name.split()[:2]) if len(target_name.split()) > 2 else target_name,
        ''.join(target_name.split()),
        '.'.join(target_name.split()),
        '_'.join(target_name.split())
    ]
    
    name_parts = target_name.split()
    if len(name_parts) > 1:
        name_variations.append(name_parts[0])
        name_variations.append(name_parts[-1])
    
    for platform in SOCIAL_MEDIA_SITES:
        print(f"\n🌐 Searching: {platform['name']}")
        platform_results = []
        
        for name_variation in name_variations:
            query = f"{name_variation} {platform['site']}"
            
            if 'exclude' in platform:
                query += f" {platform['exclude']}"
                
            print(f"  Trying query: {query}")
            search_results = google_search(query)
            
            if search_results:
                print(f"  Found {len(search_results)} potential results")
                
                for result in search_results:
                    link = result.get('link', '')
                    username = extract_username(link, platform['username_pattern'])
                    
                    relevance_score = score_profile_relevance(result, target_name)
                    
                    name_related = is_name_related(result, target_name)
                    
                    if username and (name_related or relevance_score >= 1):
                        if not any(r.get('username') == username for r in platform_results):
                            result_data = {
                                "title": result.get('title', ''),
                                "url": link,
                                "snippet": result.get('snippet', ''),
                                "username": username,
                                "relevance_score": relevance_score,
                                "name_match": name_related
                            }
                            
                            platform_results.append(result_data)
                            print(f"  ✅ Found profile: {username} (Relevance: {relevance_score}/7, Name match: {'Yes' if name_related else 'No'})")
            
            if len(platform_results) >= 5:
                break
        
        if platform_results:
            platform_results.sort(key=lambda x: (x.get('name_match', False), x.get('relevance_score', 0)), reverse=True)
            top_results = platform_results[:8]
            
            all_results.append({
                "platform": platform['name'],
                "profile_type": platform.get('profile_type', 'social'),
                "results": top_results
            })
    
    return all_results

def save_results(data, filename_base):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{filename_base}_{timestamp}.json"
        filepath = os.path.join(OUTPUT_DIR, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, indent=4, ensure_ascii=False)
        
        print(f"📂 Data saved to {filepath}")
        return filepath
    
    except Exception as e:
        print(f"❌ Error saving data: {e}")
        return None

def run_osint():
    print("\n" + "="*50)
    print("🔍 Simple OSINT Tool 🔍")
    print("="*50)
    
    target_name = input("\n👤 Enter target name/username for investigation: ")
    if not target_name:
        print("❌ No target specified. Exiting.")
        return
    
    investigation_data = {
        "target": target_name,
        "timestamp": datetime.now().isoformat(),
        "twitter_data": {},
        "social_media_profiles": []
    }
    
    while True:
        print("\n" + "-"*50)
        print("📋 OSINT Menu:")
        print("-"*50)
        print("1. Twitter Profile Analysis")
        print("2. Simple Twitter Search")
        print("3. Social Media Profile Search")
        print("4. Save All Data")
        print("0. Exit")
        
        choice = input("\nSelect an option (0-4): ")
        
        if choice == "1":
            if not twitter_client:
                print("❌ Twitter operations not available - API client initialization failed")
                continue
                
            print("\n🐦 Twitter Profile Analysis")
            twitter_username = input(f"Enter Twitter username (default: {target_name}): ") or target_name
                
            print(f"📊 Analyzing Twitter profile: @{twitter_username}...")
            user_info = get_twitter_user_info(twitter_username)
            
            if user_info:
                print("\n✅ Twitter Profile Data:")
                for key, value in user_info.items():
                    print(f"  {key}: {value}")
                
                save_results(user_info, f"twitter_profile_{twitter_username}")
                
                investigation_data["twitter_data"]["profile"] = user_info
                
                follow_up = input("\nDo you want to analyze tweets from this user? (y/n): ").lower()
                
                if follow_up == "y":
                    print(f"🔍 Searching for tweets from @{twitter_username}...")
                    tweets = search_tweets(f"from:{twitter_username}")
                    
                    if tweets:
                        print(f"✅ Found {len(tweets)} tweets")
                        save_results(tweets, f"tweets_from_{twitter_username}")
                        investigation_data["twitter_data"]["tweets"] = tweets
            else:
                print(f"❌ Could not find Twitter profile for @{twitter_username}")
        
        elif choice == "2":
            if not twitter_client:
                print("❌ Twitter operations not available - API client initialization failed")
                continue
                
            print("\n🔎 Twitter Search")
            query = input("Enter search keywords: ")
            
            if not query:
                print("❌ No search terms provided")
                continue
            
            max_tweets = input("Maximum number of tweets to retrieve (default 50): ") or "50"
            try:
                max_tweets = int(max_tweets)
            except ValueError:
                max_tweets = 50
                print("Invalid number, using default of 50 tweets.")
            
            print(f"\n🔍 Searching for: {query}")
            tweets = search_tweets(query, max_tweets)
            
            if tweets:
                print(f"✅ Found {len(tweets)} tweets")
                filename_base = query.replace(" ", "_").replace(":", "").replace("\"", "")[:30]
                save_results(tweets, f"tweets_{filename_base}")
                
                if "searches" not in investigation_data:
                    investigation_data["searches"] = []
                
                investigation_data["searches"].append({
                    "platform": "twitter",
                    "query": query,
                    "timestamp": datetime.now().isoformat(),
                    "results": tweets
                })
            else:
                print("❌ No tweets found matching your query")
        
        elif choice == "3":
            print("\n🌐 Social Media Profile Search")
            search_name = input(f"Enter name to search (default: {target_name}): ") or target_name
            
            print(f"\n🔍 Searching for social media profiles: {search_name}")
            print("⚠ This may take a moment as multiple search strategies are used...")
            
            social_results = social_media_lookup(search_name)
            
            if social_results:
                total_profiles = sum(len(platform["results"]) for platform in social_results)
                print(f"\n✅ Found {total_profiles} potential profiles across {len(social_results)} platforms")
                
                print("\n📊 Summary of findings:")
                for platform in social_results:
                    profile_count = len(platform["results"])
                    if profile_count > 0:
                        print(f"  {platform['platform']}: {profile_count} profiles")
                        for profile in platform["results"]:
                            name_match = profile.get('name_match', False)
                            match_info = "⭐ Name match" if name_match else ""
                            print(f"    - {profile.get('username', 'Unknown')} (Score: {profile.get('relevance_score')}/7) {match_info}")
                
                save_results(social_results, f"social_profiles_{search_name}")
                
                investigation_data["social_media_profiles"] = social_results
            else:
                print("❌ No social media profiles found")
        
        elif choice == "4":
            print("\n💾 Save Complete Investigation Data")
            
            total_profiles = sum(len(platform["results"]) for platform in investigation_data["social_media_profiles"]) if investigation_data["social_media_profiles"] else 0
            
            summary = {
                "target": target_name,
                "timestamp": datetime.now().isoformat(),
                "twitter_profile_analyzed": "profile" in investigation_data["twitter_data"],
                "twitter_tweets_analyzed": "tweets" in investigation_data["twitter_data"],
                "social_platforms_found": len(investigation_data["social_media_profiles"]),
                "total_profiles_found": total_profiles
            }
            
            investigation_data["summary"] = summary
            
            clean_name = target_name.replace(" ", "_").lower()
            filepath = save_results(investigation_data, f"investigation_{clean_name}")
            
            if filepath:
                print(f"\n✅ Complete investigation data saved to: {filepath}")
            else:
                print("❌ Failed to save investigation data")
        
        elif choice == "0":
            print("\n📊 OSINT Investigation Summary:")
            print(f"- Target: {target_name}")
            
            if "profile" in investigation_data["twitter_data"]:
                print("- Twitter profile analyzed: Yes")
            
            if "tweets" in investigation_data["twitter_data"]:
                print(f"- Twitter tweets collected: Yes")
            
            total_profiles = sum(len(platform["results"]) for platform in investigation_data["social_media_profiles"]) if investigation_data["social_media_profiles"] else 0
            print(f"- Social platforms investigated: {len(investigation_data['social_media_profiles'])}")
            print(f"- Total potential profiles found: {total_profiles}")
            print(f"\n🗂 Results saved to the {OUTPUT_DIR} directory")
            print("\n👋 OSINT investigation complete. Exiting...")
            break
        
        else:
            print("❌ Invalid option, please try again")

if __name__ == "__main__":
    run_osint()
