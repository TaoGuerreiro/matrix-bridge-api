#!/usr/bin/env python3
"""
Test script to verify production API and key persistence
"""
import asyncio
import httpx
import json
from loguru import logger

PRODUCTION_URL = "https://beeper-v2.cleverapps.io"

async def test_production_api():
    """Test all production endpoints"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        results = {}

        # Test 1: Health endpoint
        logger.info("Testing health endpoint...")
        try:
            response = await client.get(f"{PRODUCTION_URL}/api/v1/health")
            results['health'] = {
                'status_code': response.status_code,
                'content': response.text[:500] if response.text else None
            }
            if response.status_code == 200:
                data = response.json()
                logger.success(f"✅ Health check passed: {data}")
            else:
                logger.warning(f"⚠️ Health check returned {response.status_code}")
        except Exception as e:
            results['health'] = {'error': str(e)}
            logger.error(f"❌ Health check failed: {e}")

        # Test 2: Test endpoint
        logger.info("Testing test endpoint...")
        try:
            response = await client.get(f"{PRODUCTION_URL}/api/v1/test")
            results['test'] = {
                'status_code': response.status_code,
                'content': response.text[:500] if response.text else None
            }
            if response.status_code == 200:
                logger.success(f"✅ Test endpoint passed")
            else:
                logger.warning(f"⚠️ Test endpoint returned {response.status_code}")
        except Exception as e:
            results['test'] = {'error': str(e)}
            logger.error(f"❌ Test endpoint failed: {e}")

        # Test 3: Rooms endpoint
        logger.info("Testing rooms endpoint...")
        try:
            response = await client.get(f"{PRODUCTION_URL}/api/v1/rooms")
            results['rooms'] = {
                'status_code': response.status_code,
                'content': response.text[:500] if response.text else None
            }
            if response.status_code == 200:
                data = response.json()
                logger.success(f"✅ Rooms endpoint passed, found {len(data.get('rooms', []))} rooms")
            else:
                logger.warning(f"⚠️ Rooms endpoint returned {response.status_code}")
        except Exception as e:
            results['rooms'] = {'error': str(e)}
            logger.error(f"❌ Rooms endpoint failed: {e}")

        # Test 4: Instagram messages endpoint
        logger.info("Testing Instagram messages endpoint...")
        try:
            response = await client.get(f"{PRODUCTION_URL}/api/v1/messages/instagram")
            results['instagram_messages'] = {
                'status_code': response.status_code,
                'content': response.text[:500] if response.text else None
            }
            if response.status_code == 200:
                data = response.json()
                logger.success(f"✅ Instagram messages endpoint passed")
                if 'messages' in data:
                    logger.info(f"   Found {len(data['messages'])} messages")
            else:
                logger.warning(f"⚠️ Instagram messages returned {response.status_code}")
        except Exception as e:
            results['instagram_messages'] = {'error': str(e)}
            logger.error(f"❌ Instagram messages failed: {e}")

        # Summary
        logger.info("\n📊 Test Summary:")
        for endpoint, result in results.items():
            if 'error' in result:
                logger.error(f"   {endpoint}: ❌ Failed - {result['error']}")
            elif result.get('status_code') == 200:
                logger.success(f"   {endpoint}: ✅ Success")
            elif result.get('status_code') == 404:
                logger.warning(f"   {endpoint}: ⚠️ Not Found (404)")
            else:
                logger.warning(f"   {endpoint}: ⚠️ Status {result.get('status_code')}")

        return results

if __name__ == "__main__":
    asyncio.run(test_production_api())