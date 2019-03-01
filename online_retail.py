#!/usr/bin/python
# -*- coding: utf-8 -*-

import pandas as pd
import numpy as np
import pymysql
import pandas.io.sql as psql
import scipy.spatial as sp
import time

# test
# データベースへ接続
con = pymysql.connect(
    host='datamix-school-material.csbsmnjyxb52.ap-northeast-1.rds.amazonaws.com',
    user='user1',
    password='user1',
    db='online_retail',
    charset='utf8mb4',
    cursorclass=pymysql.cursors.DictCursor)

def main():
    # Enter your code
    pass


# SQLによるデータ抽出
def extract_data():
    sql = """
        SELECT
        b.customer_id, b.stock_code, b.description, b.quantity
        FROM (
            -- 顧客IDと商品コードでGROUP BY
            SELECT
            CustomerID AS customer_id,
            StockCode AS stock_code,
            Description AS description,
            SUM(Quantity) AS quantity
            FROM sales_log

            -- キャンセルされた取引（InvoiceNoがCから始まるもの）は除く
            WHERE InvoiceNo NOT LIKE "C%"
            
            -- 価格(UnitPrice)が0のものは除く ※廃棄処分された記録など
            AND UnitPrice > 0
            
            -- 顧客名が欠損しているものは除く
            AND CustomerID != ""

            GROUP BY CustomerID, StockCode
            
        ) AS b

        INNER JOIN (
            SELECT
            a.stock_code,
            COUNT(DISTINCT description) AS cnt
            FROM (
                SELECT
                StockCode AS stock_code,
                Description AS description
                FROM sales_log
                GROUP BY StockCode, description
            ) AS a
            GROUP BY a.stock_code
            
            -- 商品コードと商品説明分が1対1でないものは除く
            HAVING cnt = 1
            
        ) AS c
        ON b.stock_code = c.stock_code
    """
    
    return psql.read_sql(con=con, sql=sql)


# 顧客ID×商品コードのテーブルを作成
def make_customer_stock_matrix(data):
    customer_stock_matrix = pd.pivot_table(data, index='customer_id', columns='description', values='quantity')
    customer_stock_matrix.fillna(0, inplace=True)
    return customer_stock_matrix


# コサイン類似度を計算する関数
def get_cosine_similarity(x, y):  
    return 1- sp.distance.cosine(x, y)


# 顧客リスト（customer_list）から、レコメンドしたい顧客のindexを取り出す関数
def get_customer_list_index(customer_list, target_customer_id):
    for index in range(len(customer_list)):
        if customer_list[index] == target_customer_id:
            target_customer_index = index
    return target_customer_index


# レコメンドしたい顧客と、全顧客との類似度を計算する関数
def get_user_similarity(customer_stock_matrix_array, target_customer_index):
    user_similarity = []
    target_user_row = customer_stock_matrix_array[target_customer_index]

    for row in customer_stock_matrix_array:
        similarity = get_cosine_similarity(target_user_row, row)
        user_similarity.append(similarity)

    user_similarity = np.array(user_similarity)
    return user_similarity


# 商品の平均類似度を計算する関数
def get_average_score_of_item(user_similarity, customer_stock_matrix_array, user_top_N):
    # TopN人の類似度と購入数量行列を取得
    idx = user_similarity.argsort()[::-1][1:user_top_N+1]
    selected_user_similarity = user_similarity[idx]
    selected_matrix = customer_stock_matrix_array[idx]
    
    # ユーザーTopN人を対象に、商品ごとの平均類似度を計算
    avg_score = []
    for col_idx in range(selected_matrix.shape[1]):
        weight_score = sum(selected_matrix[:, col_idx] * selected_user_similarity)
        similarity_sum = sum(selected_user_similarity[selected_user_similarity > 0])
        avg_score.append(weight_score / similarity_sum)
    avg_score = np.array(avg_score)
    return avg_score


# 平均類度の高い上位N商品をオススメとして表示する関数
def print_recommendation_items(stock_list, average_score_of_item, already_ordered_product, recommend_top_N):
    counter = 0
    print("■レコメンド商品リスト:")
    for recommended_product in stock_list[average_score_of_item.argsort()[::-1]]:
        if recommended_product not in already_ordered_product:
            print(counter+1,recommended_product)
            counter += 1
            if recommend_top_N <= counter:
                break


# レコメンドをする関数
def recommend(target_customer_id, customer_stock_matrix, user_top_N, recommend_top_N):
    # Pandas Dataframeから、index, columns, 行列を取得
    stock_list = customer_stock_matrix.columns
    customer_list = customer_stock_matrix.index
    customer_stock_matrix_array = np.array(customer_stock_matrix)
    
    # あるレコメンドしたい顧客IDを引数とした際に、顧客リスト（customer_list）から、レコメンドしたい顧客のindexを取り出す
    target_customer_index = get_customer_list_index(customer_list, target_customer_id)
    
    # レコメンドしたい顧客と、全顧客との類似度を計算する
    user_similarity = get_user_similarity(customer_stock_matrix_array, target_customer_index)
    
    # レコメンドしたい顧客に対してコサイン類似度の高いユーザーTopN人を対象に、商品の平均類似度を計算する
    average_score_of_item = get_average_score_of_item(user_similarity, customer_stock_matrix_array, user_top_N)
    
    # レコメンドする必要がない、既に購入済の商品リストを抽出
    already_ordered_product = stock_list[np.where(customer_stock_matrix[customer_stock_matrix.index == target_customer_id])[1]]
    
    # 平均類度の高い上位N商品をオススメとして表示する
    print_recommendation_items(stock_list, average_score_of_item, already_ordered_product, recommend_top_N)


if __name__ == "__main__":
    main()
