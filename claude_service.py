# claude_service.py
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
    
    async def analyze_data(self, user_query: str, df: pd.DataFrame, request_type: str, session_id: int = None) -> Dict[str, Any]:        
        """
        Analyze data using Claude and return response with visualizations
        """
        
        # Get data summary for Claude
        data_summary = self._get_data_summary(df)
        
        # Create prompt based on request type
        prompt = self._create_prompt(user_query, data_summary, request_type, df)
        
        try:
            # Call Claude API - MODÈLE MIS À JOUR
            response = self.client.messages.create(
                model="claude-3-5-sonnet-20241022",
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
    
    async def create_full_dashboard(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Create a comprehensive dashboard with KPIs, charts, and filters"""
        
        try:
            # Analyse des types de colonnes
            numeric_cols = df.select_dtypes(include=['int64', 'float64']).columns.tolist()
            categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
            date_cols = []
            
            # Détection des colonnes de dates
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        pd.to_datetime(df[col].dropna().head(100), errors='raise')
                        date_cols.append(col)
                        if col in categorical_cols:
                            categorical_cols.remove(col)
                    except:
                        continue
            
            # 1. GÉNÉRATION DES KPIs
            kpis = self._generate_kpis(df, numeric_cols, categorical_cols, date_cols)
            
            # 2. GÉNÉRATION DES GRAPHIQUES
            charts = self._generate_charts(df, numeric_cols, categorical_cols, date_cols)
            
            # 3. GÉNÉRATION DES FILTRES
            filters = self._generate_filters(df, numeric_cols, categorical_cols, date_cols)
            
            # 4. RÉSUMÉ DES DONNÉES
            data_summary = self._generate_data_summary(df, numeric_cols, categorical_cols, date_cols)
            
            return {
                "kpis": kpis,
                "charts": charts,
                "filters": filters,
                "summary": data_summary,
                "metadata": {
                    "total_rows": len(df),
                    "total_columns": len(df.columns),
                    "numeric_columns": len(numeric_cols),
                    "categorical_columns": len(categorical_cols),
                    "date_columns": len(date_cols)
                }
            }
            
        except Exception as e:
            print(f"Erreur lors de la création du dashboard: {e}")
            return {
                "kpis": [],
                "charts": [],
                "filters": [],
                "summary": {},
                "error": str(e)
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

    def _generate_kpis(self, df: pd.DataFrame, numeric_cols: list, categorical_cols: list, date_cols: list) -> list:
        """Génère les KPIs principaux"""
        kpis = []
        
        # KPI 1: Nombre total d'enregistrements
        kpis.append({
            "id": "total_records",
            "title": "Total Records",
            "value": int(len(df)),  # ✅ Conversion explicite
            "format": "number",
            "icon": "database",
            "color": "blue"
        })
    
        # KPI 2: Première colonne numérique
        if numeric_cols:
            main_numeric = numeric_cols[0]
            total_value = float(df[main_numeric].sum())  # ✅ Conversion explicite
            kpis.append({
                "id": "main_metric", 
                "title": f"Total {main_numeric}",
                "value": total_value,
                "format": "currency" if any(word in main_numeric.lower() for word in ['price', 'cost', 'revenue', 'sales']) else "number",
                "icon": "trending-up",
                "color": "green"
            })
        
            # KPI 3: Moyenne
            avg_value = float(df[main_numeric].mean())  # ✅ Conversion explicite
            kpis.append({
                "id": "avg_metric",
                "title": f"Average {main_numeric}", 
                "value": round(avg_value, 2),
                "format": "currency" if any(word in main_numeric.lower() for word in ['price', 'cost', 'revenue', 'sales']) else "number",
                "icon": "bar-chart",
                "color": "purple"
            })
    
            # KPI 4: Catégories uniques
            if categorical_cols:
                main_categorical = categorical_cols[0]
                unique_count = int(df[main_categorical].nunique())  # ✅ Conversion explicite
                kpis.append({
                    "id": "unique_categories",
                    "title": f"Unique {main_categorical}",
                    "value": unique_count,
                    "format": "number", 
                    "icon": "tag",
                    "color": "orange"
                })
        return kpis

    def _generate_charts(self, df: pd.DataFrame, numeric_cols: list, categorical_cols: list, date_cols: list) -> list:
        """Génère les graphiques pour le dashboard"""
        charts = []
        
        try:
            # Chart 1: Distribution de la première colonne numérique
            if numeric_cols:
                col = numeric_cols[0]
                fig = px.histogram(
                    df, 
                    x=col, 
                    title=f"Distribution of {col}",
                    nbins=20,
                    color_discrete_sequence=['#3B82F6']
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#374151')
                )
                charts.append({
                    "id": "distribution_chart",
                    "title": f"Distribution of {col}",
                    "type": "histogram",
                    "data": fig.to_json(),
                    "position": {"row": 1, "col": 1}
                })
            
            # Chart 2: Top 10 de la première colonne catégorielle
            if categorical_cols:
                col = categorical_cols[0]
                value_counts = df[col].value_counts().head(10)
                fig = px.bar(
                    x=value_counts.index, 
                    y=value_counts.values,
                    title=f"Top 10 {col}",
                    color=value_counts.values,
                    color_continuous_scale='Blues'
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#374151'),
                    xaxis_title=col,
                    yaxis_title="Count"
                )
                charts.append({
                    "id": "top_categories",
                    "title": f"Top 10 {col}",
                    "type": "bar",
                    "data": fig.to_json(),
                    "position": {"row": 1, "col": 2}
                })
            
            # Chart 3: Correlation matrix si plusieurs colonnes numériques
            if len(numeric_cols) >= 2:
                corr_matrix = df[numeric_cols[:5]].corr()  # Max 5 colonnes pour lisibilité
                fig = px.imshow(
                    corr_matrix,
                    text_auto=True,
                    title="Correlation Matrix",
                    color_continuous_scale='RdBu',
                    aspect="auto"
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#374151')
                )
                charts.append({
                    "id": "correlation_matrix",
                    "title": "Correlation Matrix",
                    "type": "heatmap",
                    "data": fig.to_json(),
                    "position": {"row": 2, "col": 1}
                })
            
            # Chart 4: Scatter plot si au moins 2 colonnes numériques
            if len(numeric_cols) >= 2:
                x_col, y_col = numeric_cols[0], numeric_cols[1]
                color_col = categorical_cols[0] if categorical_cols else None
                
                fig = px.scatter(
                    df,
                    x=x_col,
                    y=y_col,
                    color=color_col,
                    title=f"{x_col} vs {y_col}",
                    opacity=0.7
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#374151')
                )
                charts.append({
                    "id": "scatter_plot",
                    "title": f"{x_col} vs {y_col}",
                    "type": "scatter",
                    "data": fig.to_json(),
                    "position": {"row": 2, "col": 2}
                })
            
            # Chart 5: Time series si colonne de date
            if date_cols and numeric_cols:
                date_col = date_cols[0]
                numeric_col = numeric_cols[0]
                
                # Convertir en datetime et grouper par mois
                df_temp = df.copy()
                df_temp[date_col] = pd.to_datetime(df_temp[date_col], errors='coerce')
                df_temp = df_temp.dropna(subset=[date_col])
                
                if len(df_temp) > 0:
                    monthly_data = df_temp.groupby(df_temp[date_col].dt.to_period('M'))[numeric_col].sum().reset_index()
                    monthly_data[date_col] = monthly_data[date_col].astype(str)
                    
                    fig = px.line(
                        monthly_data,
                        x=date_col,
                        y=numeric_col,
                        title=f"{numeric_col} Over Time",
                        markers=True
                    )
                    fig.update_layout(
                        plot_bgcolor='rgba(0,0,0,0)',
                        paper_bgcolor='rgba(0,0,0,0)',
                        font=dict(color='#374151')
                    )
                    charts.append({
                        "id": "time_series",
                        "title": f"{numeric_col} Over Time",
                        "type": "line",
                        "data": fig.to_json(),
                        "position": {"row": 3, "col": 1}
                    })
            
            # Chart 6: Box plot pour outliers
            if numeric_cols:
                col = numeric_cols[0]
                fig = px.box(
                    df,
                    y=col,
                    title=f"Box Plot - {col} (Outlier Detection)",
                    color_discrete_sequence=['#10B981']
                )
                fig.update_layout(
                    plot_bgcolor='rgba(0,0,0,0)',
                    paper_bgcolor='rgba(0,0,0,0)',
                    font=dict(color='#374151')
                )
                charts.append({
                    "id": "box_plot",
                    "title": f"Box Plot - {col}",
                    "type": "box",
                    "data": fig.to_json(),
                    "position": {"row": 3, "col": 2}
                })
                
        except Exception as e:
            print(f"Erreur génération graphiques: {e}")
            
        return charts

    def _generate_filters(self, df: pd.DataFrame, numeric_cols: list, categorical_cols: list, date_cols: list) -> list:
        """Génère les filtres possibles"""
        filters = []
        
        # Filtres pour colonnes catégorielles
        for col in categorical_cols[:3]:  # Max 3 pour éviter surcharge
            unique_values = df[col].dropna().unique().tolist()
            if len(unique_values) <= 50:  # Eviter trop d'options
                filters.append({
                    "id": f"filter_{col}",
                    "column": col,
                    "type": "multiselect",
                    "label": f"Filter by {col}",
                    "options": [{"value": val, "label": str(val)} for val in sorted(unique_values)],
                    "default": []
                })
        
        # Filtres pour colonnes numériques (range)
        for col in numeric_cols[:2]:  # Max 2 ranges
            min_val = float(df[col].min())
            max_val = float(df[col].max())
            filters.append({
                "id": f"range_{col}",
                "column": col,
                "type": "range",
                "label": f"{col} Range",
                "min": min_val,
                "max": max_val,
                "default": [min_val, max_val],
                "step": (max_val - min_val) / 100
            })
        
        # Filtres pour dates
        for col in date_cols[:1]:  # Max 1 date filter
            try:
                df_temp = df.copy()
                df_temp[col] = pd.to_datetime(df_temp[col], errors='coerce')
                df_clean = df_temp.dropna(subset=[col])
                
                if len(df_clean) > 0:
                    min_date = df_clean[col].min().strftime('%Y-%m-%d')
                    max_date = df_clean[col].max().strftime('%Y-%m-%d')
                    
                    filters.append({
                        "id": f"date_{col}",
                        "column": col,
                        "type": "daterange",
                        "label": f"Date Range - {col}",
                        "min": min_date,
                        "max": max_date,
                        "default": [min_date, max_date]
                    })
            except:
                continue
        
        return filters

    def _generate_data_summary(self, df: pd.DataFrame, numeric_cols: list, categorical_cols: list, date_cols: list) -> dict:
        """Génère un résumé des données"""
        
        summary = {
            "overview": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "missing_values": df.isnull().sum().sum(),
                "duplicate_rows": df.duplicated().sum(),
                "memory_usage": f"{df.memory_usage(deep=True).sum() / 1024**2:.2f} MB"
            },
            "column_types": {
                "numeric": len(numeric_cols),
                "categorical": len(categorical_cols), 
                "datetime": len(date_cols)
            },
            "data_quality": {
                "completeness": f"{((len(df) * len(df.columns) - df.isnull().sum().sum()) / (len(df) * len(df.columns)) * 100):.1f}%",
                "uniqueness": f"{(len(df) - df.duplicated().sum()) / len(df) * 100:.1f}%"
            }
        }
        
        # Statistiques numériques
        if numeric_cols:
            numeric_stats = {}
            for col in numeric_cols[:5]:  # Top 5 numeric columns
                numeric_stats[col] = {
                    "mean": round(df[col].mean(), 2),
                    "median": round(df[col].median(), 2),
                    "std": round(df[col].std(), 2),
                    "min": round(df[col].min(), 2),
                    "max": round(df[col].max(), 2)
                }
            summary["numeric_stats"] = numeric_stats
        
        # Top catégories
        if categorical_cols:
            categorical_stats = {}
            for col in categorical_cols[:3]:  # Top 3 categorical columns
                top_values = df[col].value_counts().head(5)
                categorical_stats[col] = {
                    "unique_count": df[col].nunique(),
                    "top_values": top_values.to_dict(),
                    "most_frequent": top_values.index[0] if len(top_values) > 0 else None
                }
            summary["categorical_stats"] = categorical_stats
        
        return summary
    
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
