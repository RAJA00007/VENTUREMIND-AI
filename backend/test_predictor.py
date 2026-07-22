from ml.predictor import startup_predictor



if __name__ == '__main__':
    result = startup_predictor.predict(
    
        industry="AI",
    
        funding=500,
    
        employees=300,
    
        age=5,
    
        revenue=50,
    
        growth=60
    
    )
    
    
    
    print(result)