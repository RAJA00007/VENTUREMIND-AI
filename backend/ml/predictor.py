import joblib

import pandas as pd

from pathlib import Path



BASE_DIR = Path(__file__).parent



class StartupPredictor:


    def __init__(self):


        self.model = joblib.load(
            BASE_DIR / "startup_success_model.pkl"
        )


        self.encoder = joblib.load(
            BASE_DIR / "industry_encoder.pkl"
        )



    def predict(
        self,
        industry: str,
        funding: float,
        employees: int,
        age: int,
        revenue: float,
        growth: float
    ):


        try:

            industry_encoded = (
                self.encoder.transform(
                    [industry]
                )[0]
            )


        except:


            industry_encoded = 0



        data = pd.DataFrame(
            [
                {
                    "industry": industry_encoded,
                    "funding_million": funding,
                    "employees": employees,
                    "age_years": age,
                    "revenue_million": revenue,
                    "growth_rate": growth
                }
            ]
        )



        probability = (
            self.model
            .predict_proba(data)[0][1]
        )


        prediction = (
            self.model.predict(data)[0]
        )



        return {

            "success_probability":
                round(
                    probability * 100,
                    2
                ),


            "prediction":
                (
                    "Likely Success"

                    if prediction == 1

                    else "High Risk"
                )

        }




startup_predictor = StartupPredictor()