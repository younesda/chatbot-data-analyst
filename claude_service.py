from dotenv import load_dotenv
load_dotenv()  # Charge en premier

import anthropic
import pandas as pd
import json
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any
import os
import base64
import io

class ClaudeService:
    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.getenv("ANTHROPIC_API_KEY")
        )
    
    async def analyze_data(self, user_query: str, df: pd.DataFrame, request_type: str) -> Dict[str, Any]:
        """
        Analyze data using Claude and return response with visualizations
        """
        
        # Get data summary for Claude
        data_summary = self._get_data_summary(df)
        
        # Create prompt based on request type
        prompt = self._create_prompt(user_query, data_summary, request_type, df)
        
        try:
            # Call Claude API
            response = self.client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=4000,
                messages=[{
                    "role": "user", 
                    "content": prompt
                }]
            )
            
            claude_response = response.content[0].text
            
            # Generate visualization based on request and Claude's analysis
            visualization_result = self._generate_visualization(
                user_query, df, request_type, claude_response
            )
            
            return {
                "text": claude_response,
                "visualization": visualization_result.get("data"),
                "chart_config": visualization_result.get("config")
            }
            
        except Exception as e:
            return {
                "text": f"Désolé, une erreur s'est produite lors de l'analyse : {str(e)}",
                "visualization": None,
                "chart_config": None
            }
    
    def _get_data_summary(self, df: pd.DataFrame) -> str:
        """Get a summary of the dataframe for Claude"""
        summary = f"""
INFORMATIONS SUR LE DATASET:
- Forme: {df.shape[0]} lignes, {df.shape[1]} colonnes
- Colonnes: {list(df.columns)}
- Types de données: {df.dtypes.to_dict()}
- Valeurs manquantes: {df.isnull().sum().to_dict()}

APERÇU DES DONNÉES (5 premières lignes):
{df.head().to_string()}

STATISTIQUES DESCRIPTIVES:
{df.describe().to_string() if len(df.select_dtypes(include='number').columns) > 0 else "Pas de colonnes numériques"}
"""
        return summary
    
    def _create_prompt(self, user_query: str, data_summary: str, request_type: str, df: pd.DataFrame) -> str:
        """Create appropriate prompt based on request type"""
        
        base_prompt = f"""
Tu es un analyste de données expert. L'utilisateur a uploadé un fichier CSV et te demande une analyse.

{data_summary}

DEMANDE DE L'UTILISATEUR: {user_query}
TYPE DE RÉPONSE DEMANDÉE: {request_type}

"""
        
        if request_type == "dashboard":
            prompt = base_prompt + """
L'utilisateur veut un DASHBOARD. Réponds avec:
1. Une analyse complète des données principales
2. Les insights les plus importants
3. Des recommandations pour des visualisations multiples
4. Des métriques clés à surveiller

Sois détaillé et fournis une vue d'ensemble complète des données.
"""
        
        elif request_type == "chart":
            prompt = base_prompt + """
L'utilisateur veut un GRAPHIQUE spécifique. Réponds avec:
1. Une analyse ciblée sur l'aspect demandé
2. Le type de graphique le plus approprié
3. Quelles colonnes utiliser pour l'axe X et Y
4. Des insights sur ce que le graphique révèle

Concentre-toi sur la meilleure façon de visualiser l'information demandée.
"""
        
        elif request_type == "table":
            prompt = base_prompt + """
L'utilisateur veut un TABLEAU. Réponds avec:
1. Une analyse des données tabulaires
2. Quelles colonnes sont les plus importantes
3. Des suggestions de tri ou filtrage
4. Des patterns dans les données

Concentre-toi sur l'organisation et la présentation des données sous forme tabulaire.
"""
        
        else:  # explanation
            prompt = base_prompt + """
L'utilisateur veut une EXPLICATION. Réponds avec:
1. Une explication claire et pédagogique
2. Des contextes et interprétations
3. Des liens entre différents éléments des données
4. Des recommandations d'actions

Sois didactique et accessible dans tes explications.
"""
        
        return prompt
    
    def _generate_visualization(self, user_query: str, df: pd.DataFrame, request_type: str, claude_response: str) -> Dict[str, Any]:
        """Generate appropriate visualization based on request type and data"""
        
        try:
            if request_type == "dashboard":
                return self._create_dashboard(df)
            elif request_type == "chart":
                return self._create_chart(df, user_query)
            elif request_type == "table":
                return self._create_table(df)
            else:
                return {"data": None, "config": None}
                
        except Exception as e:
            print(f"Error generating visualization: {e}")
            return {"data": None, "config": None}
    
    def _create_dashboard(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create dashboard data"""
        dashboard_data = {
            "summary_stats": {},
            "charts": []
        }
        
        # Basic stats
        dashboard_data["summary_stats"] = {
            "total_rows": len(df),
            "total_columns": len(df.columns),
            "numeric_columns": len(df.select_dtypes(include='number').columns),
            "categorical_columns": len(df.select_dtypes(include='object').columns)
        }
        
        # Generate multiple charts for dashboard
        numeric_cols = df.select_dtypes(include='number').columns
        categorical_cols = df.select_dtypes(include='object').columns
        
        # Histogram for first numeric column
        if len(numeric_cols) > 0:
            col = numeric_cols[0]
            fig = px.histogram(df, x=col, title=f"Distribution de {col}")
            dashboard_data["charts"].append({
                "type": "histogram",
                "data": fig.to_json(),
                "title": f"Distribution de {col}"
            })
        
        # Bar chart for first categorical column
        if len(categorical_cols) > 0:
            col = categorical_cols[0]
            value_counts = df[col].value_counts().head(10)
            fig = px.bar(x=value_counts.index, y=value_counts.values, 
                        title=f"Top 10 - {col}")
            dashboard_data["charts"].append({
                "type": "bar",
                "data": fig.to_json(),
                "title": f"Top 10 - {col}"
            })
        
        return {
            "data": dashboard_data,
            "config": {"type": "dashboard"}
        }
    
    def _create_chart(self, df: pd.DataFrame, user_query: str) -> Dict[str, Any]:
        """Create a specific chart based on user query and data"""
        numeric_cols = df.select_dtypes(include='number').columns
        categorical_cols = df.select_dtypes(include='object').columns
        
        # Simple logic to determine chart type
        if "correlation" in user_query.lower() and len(numeric_cols) >= 2:
            # Correlation heatmap
            corr_matrix = df[numeric_cols].corr()
            fig = px.imshow(corr_matrix, text_auto=True, title="Matrice de corrélation")
            
        elif "distribution" in user_query.lower() and len(numeric_cols) > 0:
            # Distribution plot
            col = numeric_cols[0]
            fig = px.histogram(df, x=col, title=f"Distribution de {col}")
            
        elif len(numeric_cols) >= 2:
            # Scatter plot
            fig = px.scatter(df, x=numeric_cols[0], y=numeric_cols[1], 
                           title=f"{numeric_cols[0]} vs {numeric_cols[1]}")
            
        elif len(categorical_cols) > 0:
            # Bar chart
            col = categorical_cols[0]
            value_counts = df[col].value_counts().head(10)
            fig = px.bar(x=value_counts.index, y=value_counts.values, 
                        title=f"Répartition - {col}")
        else:
            return {"data": None, "config": None}
        
        return {
            "data": fig.to_json(),
            "config": {"type": "single_chart"}
        }
    
    def _create_table(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create table data"""
        # Return first 100 rows and basic info
        table_data = {
            "data": df.head(100).to_dict('records'),
            "columns": list(df.columns),
            "total_rows": len(df),
            "dtypes": df.dtypes.astype(str).to_dict()
        }
        
        return {
            "data": table_data,
            "config": {"type": "table"}
        }
