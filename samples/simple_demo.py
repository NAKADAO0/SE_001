def calculate_order_summary(prices, discount_rate, user_id=None):
    """
    计算订单总额与折扣均价 (测试用简明代码)
    包含: 除零崩溃、越界访问、未关文件句柄与裸 except 吞异常等经典风险
    """
    # 1. 致命缺陷：缺少空列表防御，导致除零异常 (ZeroDivisionError)
    avg_price = sum(prices) / len(prices)
    
    # 2. 致命缺陷：未判断列表长度，直接索引导致越界 (IndexError)
    first_item = prices[0]
    
    # 3. 高危缺陷：未关文件句柄，未用 with 上下文管理器导致资源泄漏
    log_file = open(f"order_log_{user_id}.txt", "a")
    log_file.write(f"User: {user_id}, Avg: {avg_price}, First: {first_item}\n")
    # 遗漏 log_file.close()
    
    # 4. 高危缺陷：裸 except 宽泛异常处理，掩盖未知错误
    try:
        discounted_total = avg_price * (1.0 - discount_rate)
    except:
        discounted_total = 0.0
        
    return discounted_total
