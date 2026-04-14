from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

router = APIRouter()


class City(BaseModel):
    code: str
    name: str
    name_en: str
    country: str = "中国"


class CityListResponse(BaseModel):
    cities: List[City]


# 模拟城市数据
MOCK_CITIES = [
    City(code="BJ", name="北京", name_en="Beijing"),
    City(code="SH", name="上海", name_en="Shanghai"),
    City(code="GZ", name="广州", name_en="Guangzhou"),
    City(code="SZ", name="深圳", name_en="Shenzhen"),
    City(code="HZ", name="杭州", name_en="Hangzhou"),
    City(code="NJ", name="南京", name_en="Nanjing"),
    City(code="WH", name="武汉", name_en="Wuhan"),
    City(code="CD", name="成都", name_en="Chengdu"),
    City(code="XA", name="西安", name_en="Xi'an"),
    City(code="CQ", name="重庆", name_en="Chongqing"),
    City(code="TJ", name="天津", name_en="Tianjin"),
    City(code="SU", name="苏州", name_en="Suzhou"),
]


@router.get("/cities", response_model=CityListResponse)
def get_cities():
    """获取所有城市列表"""
    return CityListResponse(cities=MOCK_CITIES)
