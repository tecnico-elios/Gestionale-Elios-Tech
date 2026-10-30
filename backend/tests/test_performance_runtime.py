import asyncio
import unittest

from performance_runtime import AsyncTTLCache, _build_list_query


class _Auth:
    ROLE_ADMIN = "admin"

    @staticmethod
    def is_master_user(current):
        return False

    @staticmethod
    def has_permission(current, resource, action):
        return False


class PerformanceRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_cache_single_flight_runs_factory_once(self):
        cache = AsyncTTLCache(max_entries=16)
        calls = 0

        async def factory():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return {"ok": True}

        results = await asyncio.gather(*[
            cache.get_or_set("same-key", 5, factory)
            for _ in range(20)
        ])

        self.assertEqual(calls, 1)
        self.assertEqual(results, [{"ok": True}] * 20)

    async def test_cache_ttl_expires(self):
        cache = AsyncTTLCache(max_entries=16)
        await cache.set("x", 1, 0.1)
        self.assertEqual(await cache.get("x"), 1)
        await asyncio.sleep(0.12)
        self.assertIsNone(await cache.get("x"))

    def test_client_query_escapes_user_regex_and_excludes_archived(self):
        query = _build_list_query(
            "clienti",
            "Rossi.*",
            include_archived=False,
            current={"role": "user"},
            auth_mod=_Auth,
        )
        self.assertIn("$and", query)
        text_clause = query["$and"][1]
        regex = text_clause["$or"][0]["ragione_sociale"]["$regex"]
        self.assertEqual(regex, r"Rossi\.\*")

    def test_installation_query_restricts_technician(self):
        query = _build_list_query(
            "installazioni",
            None,
            include_archived=False,
            current={"_id": "u1", "username": "mario", "role": "tecnico"},
            auth_mod=_Auth,
        )
        self.assertIn("$or", query)
        self.assertIn({"tecnico_user_id": "u1"}, query["$or"])


if __name__ == "__main__":
    unittest.main()
