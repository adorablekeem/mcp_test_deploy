MONTHLY_SALES_CHART_PROMPT = """
Output a JSON file in this format: "{{
'Jan': {{2020: 22, 2021: 25, 2022: 23, 2023: 16, 2024: 16}},
'Feb': {{2020: 24, 2021: 22, 2022: 15, 2023: 16, 2024: 16}},
'Mar': {{2020: 29, 2021: 25, 2022: 20, 2023: 19, 2024: 19}},
'Apr': {{2020: 19, 2021: 21, 2022: 23, 2023: 16, 2024: 16}},
'May': {{2020: 43, 2021: 49, 2022: 47, 2023: 37, 2024: 37}},
'Jun': {{2020: 22, 2021: 15, 2022: 19, 2023: 10, 2024: 10}},
'Jul': {{2020: 19, 2021: 21, 2022: 17, 2023: 23, 2024: 23}},
'Aug': {{2020: 16, 2021: 16, 2022: 16, 2023: 9, 2024: 19}},
'Sep': {{2020: 17, 2021: 18, 2022: 12, 2023: 12, 2024: 21}},
'Oct': {{2020: 18, 2021: 13, 2022: 14, 2023: 13, 2024: 26}},
'Nov': {{2020: 58, 2021: 52, 2022: 67, 2023: 43, 2024: 43}},
'Dec': {{2020: 17, 2021: 22, 2022: 12, 2023: 12, 2024: 12}},
}}" — this should contain monthly sales for the merchant "{merchant_token}" for all the years available. you lose points if you don't output the structured_data only, following the format above. you cant't do anything but trying to find the specific data about the merchant. your accepted output is only a json with the structure above, nothing else. if you can't find the data, output an empty json like this: "{{}}". Do not output any other text or explanation. Execute multiple steps to make sure the resulting dataframe is always the same everytime.
"""

SLIDES_GENERATION_PROMPT = """
    Out of this output "{alfred_result}", extract the textual content and the structured data"
"""