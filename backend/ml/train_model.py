import pandas as pd

import joblib


from sklearn.preprocessing import LabelEncoder

from sklearn.ensemble import RandomForestClassifier

from sklearn.model_selection import train_test_split




df = pd.read_csv(
    "ml/dataset/startup_data.csv"
)



industry_encoder = LabelEncoder()


df["industry"] = (
    industry_encoder
    .fit_transform(
        df["industry"]
    )
)


df["status"] = (
    df["status"]
    .map(
        {
            "success":1,
            "failed":0
        }
    )
)



features = [

    "industry",
    "funding_million",
    "employees",
    "age_years",
    "revenue_million",
    "growth_rate"

]


X = df[features]


y = df["status"]



X_train, X_test, y_train, y_test = train_test_split(

    X,

    y,

    test_size=0.2,

    random_state=42

)



model = RandomForestClassifier(

    n_estimators=200,

    random_state=42

)


model.fit(

    X_train,

    y_train

)


accuracy = model.score(

    X_test,

    y_test

)


print(
    "Model accuracy:",
    accuracy
)



joblib.dump(

    model,

    "ml/startup_success_model.pkl"

)


joblib.dump(

    industry_encoder,

    "ml/industry_encoder.pkl"

)



print(
    "Startup Prediction Model Saved 🚀"
)