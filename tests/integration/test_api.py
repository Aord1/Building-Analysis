"""API 集成测试."""

import pytest


class TestDashboardAPI:
    """测试仪表盘 API."""

    def test_get_stats(self, client):
        """测试获取统计数据."""
        response = client.get("/api/dashboard/stats")
        assert response.status_code == 200
        data = response.json()
        assert "total_notes" in data

    def test_get_interest_points(self, client):
        """测试获取兴趣点."""
        response = client.get("/api/dashboard/interest-points")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
