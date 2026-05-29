#!/usr/bin/env python3
"""
MySQL Daily Stock Data Importer
将每日股票分析数据导入到 MySQL 数据库
"""

import mysql.connector
from mysql.connector import Error
import json
from datetime import datetime
import sys

# MySQL 连接配置
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '',  # 根据实际情况修改
    'database': 'stock_analysis',
    'raise_on_warnings': True
}

# 今日股票数据（从分析中提取）
TODAY_STOCKS = [
    {
        'code': '600098',
        'name': '广州发展',
        'date': '2026-03-26',
        'price': 8.36,
        'change_pct': 6.36,
        'pe': 9.28,
        'pb': 1.0,
        'market_cap': 358.8,
        'turnover_rate': 2.52,
        'main_flow': 0.69,
        'main_flow_pct': 9.56,
        'volume': 1089.0,
        'score': 5,
        'recommendation': '强烈推荐',
        'notes': '底部启动信号明确，主力大幅流入'
    },
    {
        'code': '600873',
        'name': '梅花生物',
        'date': '2026-03-26',
        'price': 11.48,
        'change_pct': -0.43,
        'pe': 8.04,
        'pb': 1.0,
        'market_cap': 324.2,
        'turnover_rate': 0.86,
        'main_flow': -0.43,
        'main_flow_pct': -9.80,
        'volume': 24.23,
        'score': 4,
        'recommendation': '推荐配置',
        'notes': '低估值+高分红，缩量下跌是洗盘机会'
    },
    {
        'code': '000883',
        'name': '湖北能源',
        'date': '2026-03-26',
        'price': 5.30,
        'change_pct': 0.76,
        'pe': 19.79,
        'pb': 1.0,
        'market_cap': 375.2,
        'turnover_rate': 1.80,
        'main_flow': 0.65,
        'main_flow_pct': 10.64,
        'volume': 116.5,
        'score': 4,
        'recommendation': '推荐配置',
        'notes': '主力建仓+技术启动+政策利好'
    },
    {
        'code': '600930',
        'name': '华电新能',
        'date': '2026-03-26',
        'price': 7.23,
        'change_pct': -2.56,
        'pe': 29.36,
        'pb': 1.0,
        'market_cap': 3016.0,
        'turnover_rate': 21.46,
        'main_flow': -4.77,
        'main_flow_pct': -9.51,
        'volume': 693.0,
        'score': 1,
        'recommendation': '建议回避',
        'notes': '顶部出逃信号明确，主力大幅流出'
    },
    {
        'code': '600995',
        'name': '南网储能',
        'date': '2026-03-26',
        'price': 15.93,
        'change_pct': -2.15,
        'pe': 26.64,
        'pb': 1.0,
        'market_cap': 509.1,
        'turnover_rate': 2.01,
        'main_flow': -1.18,
        'main_flow_pct': -11.68,
        'volume': 64.18,
        'score': 4,
        'recommendation': '调整中蓄势',
        'notes': '财务优秀，调整中蓄势，长期看好'
    },
    {
        'code': '600839',
        'name': '四川长虹',
        'date': '2026-03-26',
        'price': 8.66,
        'change_pct': -2.04,
        'pe': 29.78,
        'pb': 2.59,
        'market_cap': 400.2,
        'turnover_rate': 1.05,
        'main_flow': -0.58,
        'main_flow_pct': -13.63,
        'volume': 48.57,
        'score': 2,
        'recommendation': '建议观望',
        'notes': '概念炒作后回调，机构在减仓'
    },
    {
        'code': '600095',
        'name': '湘财股份',
        'date': '2026-03-26',
        'price': 9.27,
        'change_pct': -2.01,
        'pe': 56.74,
        'pb': 2.15,
        'market_cap': 263.3,
        'turnover_rate': 0.68,
        'main_flow': -0.16,
        'main_flow_pct': -9.02,
        'volume': 19.44,
        'score': 3,
        'recommendation': '中性偏谨慎',
        'notes': '高估值+板块利好，等方向明朗'
    },
    {
        'code': '600780',
        'name': '通宝能源',
        'date': '2026-03-26',
        'price': 8.45,
        'change_pct': 10.03,
        'pe': 14.90,
        'pb': 1.18,
        'market_cap': 96.65,
        'turnover_rate': 15.34,
        'main_flow': -0.55,
        'main_flow_pct': -3.90,
        'volume': 175.9,
        'score': 2,
        'recommendation': '高风险陷阱',
        'notes': '散户追高、机构出货，涨停板陷阱'
    }
]

def create_connection():
    """创建 MySQL 连接"""
    try:
        connection = mysql.connector.connect(**DB_CONFIG)
        if connection.is_connected():
            print("✅ MySQL 连接成功")
            return connection
    except Error as e:
        print(f"❌ 连接失败: {e}")
        return None

def create_tables(connection):
    """创建数据表"""
    cursor = connection.cursor()
    
    # 创建每日行情表
    create_daily_table = """
    CREATE TABLE IF NOT EXISTS stock_daily_data (
        id INT AUTO_INCREMENT PRIMARY KEY,
        code VARCHAR(10) NOT NULL,
        name VARCHAR(50) NOT NULL,
        date DATE NOT NULL,
        price DECIMAL(10, 2),
        change_pct DECIMAL(10, 2),
        pe DECIMAL(10, 2),
        pb DECIMAL(10, 2),
        market_cap DECIMAL(15, 2),
        turnover_rate DECIMAL(10, 2),
        main_flow DECIMAL(15, 2),
        main_flow_pct DECIMAL(10, 2),
        volume DECIMAL(15, 2),
        score INT,
        recommendation VARCHAR(50),
        notes TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE KEY unique_stock_date (code, date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """
    
    try:
        cursor.execute(create_daily_table)
        connection.commit()
        print("✅ 数据表创建成功")
    except Error as e:
        print(f"❌ 创建表失败: {e}")
    finally:
        cursor.close()

def insert_stock_data(connection, stocks):
    """插入股票数据"""
    cursor = connection.cursor()
    
    insert_query = """
    INSERT INTO stock_daily_data 
    (code, name, date, price, change_pct, pe, pb, market_cap, turnover_rate, 
     main_flow, main_flow_pct, volume, score, recommendation, notes)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        price = VALUES(price),
        change_pct = VALUES(change_pct),
        pe = VALUES(pe),
        pb = VALUES(pb),
        market_cap = VALUES(market_cap),
        turnover_rate = VALUES(turnover_rate),
        main_flow = VALUES(main_flow),
        main_flow_pct = VALUES(main_flow_pct),
        volume = VALUES(volume),
        score = VALUES(score),
        recommendation = VALUES(recommendation),
        notes = VALUES(notes)
    """
    
    try:
        for stock in stocks:
            values = (
                stock['code'], stock['name'], stock['date'],
                stock['price'], stock['change_pct'], stock['pe'], stock['pb'],
                stock['market_cap'], stock['turnover_rate'],
                stock['main_flow'], stock['main_flow_pct'], stock['volume'],
                stock['score'], stock['recommendation'], stock['notes']
            )
            cursor.execute(insert_query, values)
        
        connection.commit()
        print(f"✅ 成功导入 {len(stocks)} 条股票数据")
        
    except Error as e:
        print(f"❌ 数据导入失败: {e}")
        connection.rollback()
    finally:
        cursor.close()

def query_today_stocks(connection):
    """查询今日股票数据"""
    cursor = connection.cursor(dictionary=True)
    
    try:
        query = "SELECT * FROM stock_daily_data WHERE date = %s ORDER BY score DESC"
        cursor.execute(query, (datetime.now().strftime('%Y-%m-%d'),))
        
        results = cursor.fetchall()
        print(f"\n📊 今日股票数据汇总（共 {len(results)} 只）:")
        print("=" * 100)
        
        for stock in results:
            print(f"【{stock['name']}】({stock['code']})")
            print(f"  价格: ¥{stock['price']} | 涨跌: {stock['change_pct']:+.2f}% | PE: {stock['pe']:.2f}倍")
            print(f"  主力: {stock['main_flow']:+.2f}亿 ({stock['main_flow_pct']:+.2f}%) | 换手: {stock['turnover_rate']:.2f}%")
            print(f"  评分: {'⭐' * stock['score']} | 建议: {stock['recommendation']}")
            print(f"  备注: {stock['notes']}")
            print("-" * 100)
        
    except Error as e:
        print(f"❌ 查询失败: {e}")
    finally:
        cursor.close()

def main():
    """主函数"""
    print("🚀 开始导入今日股票数据到 MySQL...")
    print("=" * 100)
    
    # 创建连接
    connection = create_connection()
    if not connection:
        print("❌ 无法连接到数据库，请检查配置")
        sys.exit(1)
    
    try:
        # 创建表
        create_tables(connection)
        
        # 插入数据
        insert_stock_data(connection, TODAY_STOCKS)
        
        # 查询数据
        query_today_stocks(connection)
        
        print("\n✅ 数据导入完成！")
        
    finally:
        if connection.is_connected():
            connection.close()
            print("✅ 数据库连接已关闭")

if __name__ == '__main__':
    main()
