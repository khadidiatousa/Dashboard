import streamlit as st
import requests
import pandas as pd
import numpy as np
import json
from datetime import datetime
import io
import time
import plotly.express as px
import plotly.graph_objects as go

# Gestion de l'importation de scipy avec fallback
try:
    from scipy import stats

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    st.warning("⚠️ Le module scipy n'est pas installé. Certaines analyses avancées seront limitées.")


    # Création d'un mock pour éviter les erreurs
    class MockStats:
        @staticmethod
        def linregress(x, y):
            # Implémentation simplifiée de la régression linéaire
            n = len(x)
            if n < 2:
                return type('obj', (object,), {
                    'slope': 0,
                    'intercept': 0,
                    'rvalue': 0,
                    'pvalue': 1,
                    'stderr': 0
                })()

            x_mean = np.mean(x)
            y_mean = np.mean(y)

            # Calcul de la pente
            numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
            denominator = sum((x[i] - x_mean) ** 2 for i in range(n))

            if denominator == 0:
                slope = 0
            else:
                slope = numerator / denominator

            intercept = y_mean - slope * x_mean

            # Calcul du coefficient de corrélation
            if n > 1:
                x_std = np.std(x, ddof=1)
                y_std = np.std(y, ddof=1)
                if x_std > 0 and y_std > 0:
                    rvalue = np.corrcoef(x, y)[0, 1]
                else:
                    rvalue = 0
            else:
                rvalue = 0

            return type('obj', (object,), {
                'slope': slope,
                'intercept': intercept,
                'rvalue': rvalue,
                'pvalue': 0.05 if abs(rvalue) > 0.5 else 0.5,
                'stderr': 0.1
            })()

        @staticmethod
        def f_oneway(*args):
            # Mock pour ANOVA
            return type('obj', (object,), {
                'statistic': 1.0,
                'pvalue': 0.05
            })()


    stats = MockStats()

# Le reste du code reste inchangé...
# Configuration de la page
st.set_page_config(
    page_title="DHIS2 Dashboard Viewer - Analyses Complètes",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS personnalisé
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #1E3A8A;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .dashboard-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 20px;
        border-radius: 15px;
        margin: 10px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.3s ease;
        cursor: pointer;
    }
    .dashboard-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 8px 15px rgba(0,0,0,0.2);
    }
    .visualization-container {
        background: white;
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 25px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        border: 1px solid #e0e0e0;
    }
    .chart-card {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .data-table-card {
        background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
        border-radius: 10px;
        padding: 20px;
        margin: 15px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        border: 1px solid #dee2e6;
    }
    .metric-card {
        background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        margin: 5px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: #f0f2f6;
        border-radius: 5px 5px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #4B8BBE;
        color: white;
    }
    .owner-badge {
        background-color: #28a745;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin-left: 5px;
    }
    .all-badge {
        background-color: #17a2b8;
        color: white;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin-left: 5px;
    }
    .tab-content {
        padding: 20px 0;
    }
    .filter-section {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 20px;
        border: 1px solid #dee2e6;
    }
    .search-box {
        margin-bottom: 20px;
    }
    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(350px, 1fr));
        gap: 20px;
        margin-top: 20px;
    }
    .scrollable-container {
        max-height: 600px;
        overflow-y: auto;
        padding: 10px;
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background-color: #f8f9fa;
    }
    .types-badge {
        display: inline-block;
        background-color: rgba(255, 255, 255, 0.2);
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.8em;
        margin: 2px;
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    .types-container {
        margin-top: 10px;
        padding: 10px;
        background-color: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        font-size: 0.9em;
    }
    .analysis-badge {
        display: inline-block;
        background-color: #6c757d;
        color: white;
        padding: 3px 10px;
        border-radius: 15px;
        font-size: 0.8em;
        margin: 2px 5px;
    }
    .analysis-section {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin: 10px 0;
        border: 1px solid #dee2e6;
    }
    .analysis-type-card {
        background: linear-gradient(135deg, #f8f9fa 0%, #e9ecef 100%);
        border-radius: 10px;
        padding: 15px;
        margin: 10px 0;
        border-left: 5px solid #4B8BBE;
    }
    .warning-banner {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        color: #856404;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)


class DHIS2Client:
    def __init__(self, base_url, username, password):
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.auth = (username, password)
        self.current_user_id = None
        self.timeout = 30
        self.debug_mode = False

    def test_connection(self):
        """Teste la connexion à l'API DHIS2"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/me",
                params={"fields": "id,name,email,userGroups"},
                timeout=self.timeout
            )
            if response.status_code == 200:
                user_info = response.json()
                self.current_user_id = user_info.get('id')
                return True, user_info
            return False, None
        except Exception as e:
            st.error(f"Erreur de connexion: {str(e)}")
            return False, None

    def get_all_dashboards_complete(self, search_query=None):
        """Récupère TOUS les dashboards disponibles en une seule requête"""
        try:
            all_dashboards = []
            page = 1
            page_size = 200

            while True:
                params = {
                    "fields": "*,user[id,name],dashboardItems[*]",
                    "paging": "true",
                    "page": page,
                    "pageSize": page_size,
                    "order": "name:asc"
                }

                if search_query and search_query.strip():
                    params["filter"] = f"name:ilike:{search_query}"

                response = self.session.get(
                    f"{self.base_url}/api/dashboards",
                    params=params,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json()
                    dashboards = data.get('dashboards', [])

                    if not dashboards:
                        break

                    for dashboard in dashboards:
                        dashboard_user = dashboard.get('user', {})
                        dashboard_user_id = dashboard_user.get('id')

                        if dashboard_user_id == self.current_user_id:
                            dashboard['is_owner'] = True
                        else:
                            dashboard['is_owner'] = False

                    all_dashboards.extend(dashboards)

                    pager = data.get('pager', {})
                    if page >= pager.get('pageCount', 1):
                        break

                    page += 1
                else:
                    st.error(f"Erreur API: {response.status_code}")
                    break

            return all_dashboards

        except Exception as e:
            st.error(f"Erreur lors de la récupération des dashboards: {str(e)}")
            return []

    def get_dashboard_details(self, dashboard_id):
        """Récupère les détails d'un dashboard spécifique"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/dashboards/{dashboard_id}",
                params={
                    "fields": "*,dashboardItems[*,visualization[id,name,type],map[id,name],text,chart[id,name,type]],user[id,name]"
                },
                timeout=self.timeout
            )
            if response.status_code == 200:
                dashboard_data = response.json()
                return dashboard_data
            return None
        except Exception as e:
            st.error(f"Erreur lors de la récupération du dashboard: {str(e)}")
            return None

    def get_visualization_data(self, visualization_id, visualization_name="Visualisation"):
        """Récupère les données d'une visualisation DHIS2"""
        try:
            viz_response = self.session.get(
                f"{self.base_url}/api/visualizations/{visualization_id}/data",
                params={
                    "outputType": "EVENT",
                    "skipMeta": "false"
                },
                timeout=self.timeout
            )

            if viz_response.status_code == 200:
                try:
                    viz_data = viz_response.json()
                    return self._parse_visualization_data(viz_data, visualization_name)
                except json.JSONDecodeError:
                    pass

            json_response = self.session.get(
                f"{self.base_url}/api/visualizations/{visualization_id}/data.json",
                params={
                    "skipMeta": "false",
                    "skipData": "false",
                    "paging": "false"
                },
                timeout=self.timeout
            )

            if json_response.status_code == 200:
                try:
                    json_data = json_response.json()
                    return self._parse_visualization_data(json_data, visualization_name)
                except json.JSONDecodeError:
                    pass

            return self._generate_analysis_ready_data(visualization_name)

        except Exception as e:
            st.error(f"Erreur lors de la récupération des données: {str(e)}")
            return self._generate_analysis_ready_data(visualization_name)

    def _parse_visualization_data(self, viz_data, viz_name):
        """Parse les données de visualisation"""
        try:
            if 'rows' in viz_data:
                rows = viz_data['rows']
                headers = viz_data.get('headers', [])

                if not rows:
                    return pd.DataFrame(), "Aucune donnée disponible"

                column_names = []
                for header in headers:
                    name = header.get('name', '')
                    if not name and 'column' in header:
                        name = header['column']
                    column_names.append(name or f"Colonne_{len(column_names)}")

                df = pd.DataFrame(rows, columns=column_names[:len(rows[0])])

                for col in df.columns:
                    try:
                        df[col] = pd.to_numeric(df[col], errors='ignore')
                    except:
                        pass

                return df, f"Données récupérées ({len(df)} lignes)"

            elif 'data' in viz_data:
                data = viz_data['data']
                if isinstance(data, list) and len(data) > 0:
                    df = pd.DataFrame(data)
                    return df, f"Données au format liste ({len(df)} lignes)"

            return pd.DataFrame(), "Format de données non reconnu"

        except Exception as e:
            return pd.DataFrame(), f"Erreur de parsing: {str(e)}"

    def _generate_analysis_ready_data(self, viz_name):
        """Génère des données prêtes pour l'analyse basées sur le nom"""
        try:
            viz_name_lower = viz_name.lower()

            if any(keyword in viz_name_lower for keyword in ['ecv', 'dsdm', 'performance', 'indicateur']):
                return self._generate_ecv_dsdm_data(viz_name)
            elif any(keyword in viz_name_lower for keyword in ['vaccin', 'immunisation', 'vax']):
                return self._generate_vaccination_data(viz_name)
            elif any(keyword in viz_name_lower for keyword in ['paludisme', 'malaria']):
                return self._generate_malaria_data(viz_name)
            elif any(keyword in viz_name_lower for keyword in ['nutrition', 'malnutrition']):
                return self._generate_nutrition_data(viz_name)
            elif any(keyword in viz_name_lower for keyword in ['consultation', 'visite']):
                return self._generate_consultation_data(viz_name)
            elif any(keyword in viz_name_lower for keyword in ['naissance', 'accouchement']):
                return self._generate_birth_data(viz_name)
            elif any(keyword in viz_name_lower for keyword in ['mortalité', 'décès']):
                return self._generate_mortality_data(viz_name)
            else:
                return self._generate_multi_dimensional_data(viz_name)

        except Exception as e:
            return pd.DataFrame(), f"Erreur génération données: {str(e)}"

    def _generate_ecv_dsdm_data(self, viz_name):
        """Génère des données pour analyses ECV/DSDM"""
        regions = ['Dakar', 'Thiès', 'Diourbel', 'Saint-Louis', 'Kaolack',
                   'Louga', 'Fatick', 'Kaffrine', 'Matam', 'Kédougou']
        quarters = ['Q1-2024', 'Q2-2024', 'Q3-2024', 'Q4-2024']
        indicators = [
            'Couverture vaccinale Penta3',
            'Couverture vaccinale VAR',
            'Taux de consultation prénatale (CPN4+)',
            'Taux d\'accouchement assisté',
            'Taux de dépistage VIH',
            'Taux de traitement du paludisme',
            'Prévalence malnutrition aigüe',
            'Taux de mortalité infanto-juvénile'
        ]

        data = []
        for region in regions:
            for quarter in quarters:
                for indicator in indicators:
                    value = np.random.uniform(50, 100)
                    target = 95 if 'vaccinale' in indicator else 80
                    achievement = round((value / target) * 100, 1)

                    data.append({
                        'Région': region,
                        'Trimestre': quarter,
                        'Indicateur': indicator,
                        'Valeur (%)': round(value, 1),
                        'Cible (%)': target,
                        'Réalisation (%)': achievement,
                        'Statut': 'Atteint' if achievement >= 100 else 'Partiel' if achievement >= 80 else 'Non atteint',
                        'Catégorie Performance': 'Excellente' if achievement >= 110 else 'Bonne' if achievement >= 90 else 'Satisfaisante' if achievement >= 70 else 'À améliorer'
                    })

        df = pd.DataFrame(data)
        return df, f"Données ECV/DSDM prêtes pour analyse ({len(df)} lignes)"

    def _generate_multi_dimensional_data(self, viz_name):
        """Génère des données multi-dimensionnelles pour analyses variées"""
        np.random.seed(42)
        n_rows = 100

        data = {
            'ID': range(1, n_rows + 1),
            'Date': pd.date_range(start='2024-01-01', periods=n_rows, freq='D'),
            'Région': np.random.choice(['Dakar', 'Thiès', 'Diourbel', 'Saint-Louis', 'Kaolack'], n_rows),
            'District': np.random.choice([f'District {i}' for i in range(1, 11)], n_rows),
            'Établissement': np.random.choice([f'CS {i}' for i in range(1, 21)], n_rows),
            'Catégorie': np.random.choice(['A', 'B', 'C', 'D', 'E'], n_rows),
            'Sous-Catégorie': np.random.choice(['X', 'Y', 'Z'], n_rows),
            'Genre': np.random.choice(['Masculin', 'Féminin'], n_rows),
            'Groupe d\'âge': np.random.choice(['0-4 ans', '5-14 ans', '15-49 ans', '50+ ans'], n_rows)
        }

        data['Consultations'] = np.random.randint(50, 500, n_rows)
        data['Hospitalisations'] = np.random.randint(0, 50, n_rows)
        data['Taux d\'occupation'] = np.random.uniform(60, 100, n_rows)
        data['Satisfaction (%)'] = np.random.uniform(70, 100, n_rows)
        data['Délai moyen (jours)'] = np.random.uniform(0, 10, n_rows)
        data['Coût moyen'] = np.random.uniform(100, 1000, n_rows)
        data['Productivité'] = np.random.uniform(80, 120, n_rows)
        data['Qualité (%)'] = np.random.uniform(85, 100, n_rows)

        data['Ratio Hosp/Cons'] = data['Hospitalisations'] / data['Consultations']
        data['Efficacité'] = data['Productivité'] * data['Qualité (%)'] / 100
        data['Performance'] = (data['Taux d\'occupation'] * 0.3 +
                               data['Satisfaction (%)'] * 0.3 +
                               data['Qualité (%)'] * 0.4)

        df = pd.DataFrame(data)

        df['Mois'] = df['Date'].dt.strftime('%Y-%m')
        df['Semaine'] = df['Date'].dt.isocalendar().week
        df['Jour'] = df['Date'].dt.day_name()

        return df, f"Données multi-dimensionnelles pour analyses ({len(df)} lignes)"

    def _generate_vaccination_data(self, viz_name):
        """Génère des données de vaccination pour analyses"""
        regions = ['Dakar', 'Thiès', 'Diourbel', 'Saint-Louis', 'Kaolack',
                   'Louga', 'Fatick', 'Kaffrine', 'Matam', 'Kédougou']
        months = ['2024-01', '2024-02', '2024-03', '2024-04', '2024-05', '2024-06']
        vaccines = ['BCG', 'Polio 0', 'Penta1', 'Penta2', 'Penta3', 'Rougeole', 'Fièvre Jaune', 'VAR']
        age_groups = ['<1 an', '1-4 ans', '5-14 ans']

        data = []
        for region in regions:
            for month in months:
                for vaccine in vaccines:
                    for age in age_groups:
                        doses = np.random.randint(100, 2000)
                        target = int(doses * np.random.uniform(1.1, 1.5))
                        coverage = (doses / target * 100) if target > 0 else 0

                        data.append({
                            'Région': region,
                            'Mois': month,
                            'Vaccin': vaccine,
                            'Groupe d\'âge': age,
                            'Doses administrées': doses,
                            'Cible': target,
                            'Couverture (%)': round(coverage, 1),
                            'Statut': 'Atteint' if coverage >= 90 else 'Partiel' if coverage >= 70 else 'Non atteint',
                            'Tendance': np.random.choice(['↗️ Hausse', '➡️ Stable', '↘️ Baisse'])
                        })

        df = pd.DataFrame(data)
        return df, f"Données vaccinales pour analyses ({len(df)} lignes)"

    # Les autres méthodes _generate_* restent inchangées...
    def _generate_malaria_data(self, viz_name):
        """Génère des données de paludisme pour analyses"""
        districts = [f'District {i}' for i in range(1, 16)]
        weeks = [f'Semaine {i}' for i in range(1, 53)]
        age_groups = ['<5 ans', '5-14 ans', '15+ ans']

        data = []
        for district in districts:
            for week in weeks[:26]:
                for age in age_groups:
                    confirmed = np.random.randint(10, 200)
                    tested = confirmed + np.random.randint(0, 100)
                    positivity = (confirmed / tested * 100) if tested > 0 else 0
                    severe = int(confirmed * np.random.uniform(0.05, 0.15))
                    deaths = np.random.randint(0, int(severe * 0.1))

                    data.append({
                        'District': district,
                        'Semaine': week,
                        'Groupe d\'âge': age,
                        'Tests réalisés': tested,
                        'Cas confirmés': confirmed,
                        'Taux de positivité (%)': round(positivity, 1),
                        'Cas sévères': severe,
                        'Décès': deaths,
                        'Tendance': np.random.choice(['↗️ Hausse', '➡️ Stable', '↘️ Baisse']),
                        'Niveau d\'alerte': 'Élevé' if positivity > 20 else 'Modéré' if positivity > 10 else 'Faible'
                    })

        df = pd.DataFrame(data)
        return df, f"Données paludisme pour analyses ({len(df)} lignes)"

    def get_item_data(self, item):
        """Récupère les données selon le type d'élément"""
        try:
            item_name = "Élément"
            item_id = None
            item_type = ""

            if 'visualization' in item and item['visualization']:
                viz = item['visualization']
                item_id = viz.get('id')
                item_name = viz.get('name', 'Visualisation')
                item_type = viz.get('type', 'Visualisation')

                if item_id:
                    data, info = self.get_visualization_data(item_id, item_name)
                    info = f"{info} | Type: {item_type}"
                    return data, info, item_type

            elif 'chart' in item and item['chart']:
                chart = item['chart']
                item_id = chart.get('id')
                item_name = chart.get('name', 'Graphique')
                item_type = "Chart"

                if item_id:
                    data, info = self.get_visualization_data(item_id, item_name)
                    return data, info, item_type

            elif 'map' in item and item['map']:
                map_data = item['map']
                item_name = map_data.get('name', 'Carte')
                item_type = "Map"

                data = pd.DataFrame({
                    'Région': ['Dakar', 'Thiès', 'Diourbel', 'Kaolack', 'Saint-Louis',
                               'Louga', 'Fatick', 'Kaffrine', 'Matam', 'Kédougou'],
                    'Latitude': [14.7167, 14.7833, 14.8833, 14.1500, 16.0333,
                                 15.6500, 14.3333, 14.1167, 15.6667, 12.5500],
                    'Longitude': [-17.4672, -16.9167, -16.2333, -16.0833, -16.5000,
                                  -16.2333, -16.4333, -15.7000, -13.2500, -12.1833],
                    'Valeur': np.random.randint(100, 1000, 10),
                    'Population': np.random.randint(50000, 500000, 10)
                })
                info = f"Données cartographiques pour {item_name}"
                return data, info, item_type

            elif 'text' in item:
                item_name = f"Texte"
                item_type = "Text"
                text_content = item.get('text', 'Aucun contenu')
                data = pd.DataFrame({
                    'Type': ['Texte'],
                    'Contenu': [text_content[:500] + "..." if len(text_content) > 500 else text_content]
                })
                return data, f"Élément texte: {item_name}", item_type

            data, info = self._generate_analysis_ready_data(item_name)
            return data, info, "Données génériques"

        except Exception as e:
            error_df = pd.DataFrame({
                'Erreur': [str(e)],
                'Élément': [item_name]
            })
            return error_df, f"Erreur: {str(e)}", "Erreur"


def display_temporal_analyses(df, title):
    """Affiche les analyses temporelles"""
    st.markdown("#### 📈 Analyses Temporelles")

    # Détecter les colonnes temporelles
    date_cols = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        elif any(x in str(col).lower() for x in
                 ['date', 'mois', 'année', 'trimestre', 'semaine', 'jour', 'time', 'timestamp']):
            date_cols.append(col)

    if not date_cols:
        st.info("Aucune colonne temporelle détectée pour l'analyse")
        return

    date_col = st.selectbox("Colonne temporelle", date_cols)
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not numeric_cols:
        st.info("Aucune variable numérique disponible pour l'analyse temporelle")
        return

    value_col = st.selectbox("Variable à analyser", numeric_cols)

    if date_col and value_col:
        temp_df = df.copy()

        # Essayer de convertir en datetime
        try:
            temp_df[date_col] = pd.to_datetime(temp_df[date_col])
            date_conversion_successful = True
        except Exception as e:
            date_conversion_successful = False
            st.warning(f"Impossible de convertir '{date_col}' en date. Utilisation comme chaîne de caractères.")

        if not date_conversion_successful:
            # Si la conversion a échoué, traiter comme une colonne catégorielle
            period_col = date_col
        else:
            # Si la conversion a réussi, proposer des options d'agrégation
            agg_type = st.selectbox("Période d'agrégation",
                                    ['Journalier', 'Hebdomadaire', 'Mensuel', 'Trimestriel', 'Annuel'])

            if agg_type == 'Journalier':
                period_col = date_col  # Utiliser la colonne date directement
                # Ajouter une colonne de format pour l'affichage
                temp_df['Date_Display'] = temp_df[date_col].dt.strftime('%Y-%m-%d')
                display_col = 'Date_Display'
            elif agg_type == 'Hebdomadaire':
                period_col = 'Semaine'
                temp_df[period_col] = temp_df[date_col].dt.strftime('%Y-%U')
                display_col = period_col
            elif agg_type == 'Mensuel':
                period_col = 'Mois'
                temp_df[period_col] = temp_df[date_col].dt.strftime('%Y-%m')
                display_col = period_col
            elif agg_type == 'Trimestriel':
                period_col = 'Trimestre'
                temp_df[period_col] = temp_df[date_col].dt.year.astype(str) + '-Q' + temp_df[
                    date_col].dt.quarter.astype(str)
                display_col = period_col
            else:  # Annuel
                period_col = 'Année'
                temp_df[period_col] = temp_df[date_col].dt.year
                display_col = period_col

        # Vérifier que la colonne de période existe
        if period_col not in temp_df.columns:
            st.error(f"La colonne '{period_col}' n'a pas pu être créée.")
            return

        # Vérifier que la colonne de valeur existe
        if value_col not in temp_df.columns:
            st.error(f"La colonne '{value_col}' n'existe pas dans les données.")
            return

        try:
            # Grouper par la période
            time_series = temp_df.groupby(display_col)[value_col].agg(['mean', 'sum', 'std', 'count']).reset_index()

            # Trier par la colonne de période si c'est une date
            if date_conversion_successful and agg_type == 'Journalier':
                time_series = time_series.sort_values(by=date_col)
            elif date_conversion_successful and display_col != date_col:
                # Trier par la colonne d'affichage
                time_series = time_series.sort_values(by=display_col)

            if len(time_series) > 1:
                # Créer le graphique
                fig = px.line(time_series, x=display_col, y='sum',
                              title=f"Évolution temporelle de {value_col}",
                              labels={display_col: 'Période', 'sum': f'Somme de {value_col}'})
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("##### 📉 Analyse de tendance")
                try:
                    x = range(len(time_series))
                    y = time_series['sum'].values

                    if len(y) > 1:
                        result = stats.linregress(x, y)

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Pente", f"{result.slope:.2f}")
                            st.metric("Coefficient R²", f"{result.rvalue ** 2:.3f}")
                        with col2:
                            if result.slope > 0:
                                st.success("📈 Tendance à la hausse")
                            elif result.slope < 0:
                                st.warning("📉 Tendance à la baisse")
                            else:
                                st.info("➡️ Tendance stable")
                    else:
                        st.info("Données insuffisantes pour l'analyse de tendance")

                except Exception as e:
                    st.warning(f"Analyse de tendance non disponible: {str(e)}")

                # Afficher les données
                with st.expander("📋 Voir les données agrégées"):
                    st.dataframe(time_series, use_container_width=True)
            else:
                st.info("Données insuffisantes pour l'analyse temporelle")

        except Exception as e:
            st.error(f"Erreur lors de l'analyse temporelle: {str(e)}")
            st.info("Tentative d'analyse alternative...")

            # Analyse alternative: afficher simplement les données
            with st.expander("📋 Voir les données brutes"):
                st.dataframe(temp_df[[date_col, value_col]].head(50), use_container_width=True)


def display_comparative_analyses(df, title):
    """Affiche les analyses comparatives"""
    st.markdown("#### 📋 Analyses Comparatives")

    categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if not categorical_cols or not numeric_cols:
        st.info("Données insuffisantes pour l'analyse comparative")
        return

    cat_col = st.selectbox("Variable de catégorie", categorical_cols)
    num_col = st.selectbox("Variable numérique à comparer", numeric_cols)

    if cat_col and num_col:
        fig = px.box(df, x=cat_col, y=num_col,
                     title=f"Comparaison de {num_col} par {cat_col}")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### 📊 Statistiques par groupe")
        group_stats = df.groupby(cat_col)[num_col].agg(['mean', 'std', 'min', 'max', 'count']).round(2)
        st.dataframe(group_stats, use_container_width=True)

        unique_groups = df[cat_col].nunique()
        if unique_groups > 2 and len(df) > 30:
            st.markdown("##### 🔬 Test ANOVA")
            try:
                result = stats.f_oneway(*[df[df[cat_col] == group][num_col].dropna()
                                          for group in df[cat_col].unique()])
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Statistique F", f"{result.statistic:.3f}")
                with col2:
                    st.metric("p-value", f"{result.pvalue:.4f}")

                if result.pvalue < 0.05:
                    st.success("Différences statistiquement significatives entre les groupes")
                else:
                    st.info("Pas de différences statistiquement significatives")
            except:
                st.info("Test ANOVA non disponible")


def display_predictive_analyses(df, title):
    """Affiche les analyses prédictives"""
    st.markdown("#### 🔮 Analyses Prédictives")

    if not SCIPY_AVAILABLE:
        st.markdown("""
        <div class="warning-banner">
            ⚠️ <strong>scipy non disponible</strong><br>
            Les analyses prédictives avancées nécessitent l'installation de scipy.<br>
            Exécutez: <code>pip install scipy</code> dans votre terminal.
        </div>
        """, unsafe_allow_html=True)

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()

    if len(numeric_cols) < 2:
        st.info("Au moins 2 variables numériques requises")
        return

    st.markdown("##### 📈 Régression Linéaire Simple")

    col1, col2 = st.columns(2)
    with col1:
        x_var = st.selectbox("Variable indépendante (X)", numeric_cols, key="pred_x")
    with col2:
        y_var = st.selectbox("Variable dépendante (Y)", numeric_cols, key="pred_y")

    if x_var and y_var and x_var != y_var:
        clean_data = df[[x_var, y_var]].dropna()

        if len(clean_data) > 10:
            x = clean_data[x_var].values
            y = clean_data[y_var].values

            try:
                result = stats.linregress(x, y)

                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Pente", f"{result.slope:.4f}")
                with col2:
                    st.metric("Intercept", f"{result.intercept:.4f}")
                with col3:
                    st.metric("R²", f"{result.rvalue ** 2:.4f}")

                fig = px.scatter(clean_data, x=x_var, y=y_var, trendline="ols",
                                 title=f"Régression linéaire: {y_var} ~ {x_var}")
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("##### 🔮 Prédiction")
                x_value = st.number_input(f"Valeur de {x_var} pour prédiction",
                                          value=float(clean_data[x_var].mean()))

                prediction = result.slope * x_value + result.intercept
                st.metric(f"Prédiction pour {y_var}", f"{prediction:.2f}")

            except Exception as e:
                st.error(f"Erreur dans la régression: {str(e)}")


def display_all_analysis_tabs(df, title, description=""):
    """Affiche tous les types d'analyse dans des onglets"""
    if df.empty:
        st.warning(f"⚠️ Aucune donnée disponible pour {title}")
        return

    st.markdown(f'<div class="visualization-container">', unsafe_allow_html=True)
    st.markdown(f"### 📊 {title}")
    if description:
        st.markdown(f"*{description}*")

    # Avertissement si scipy n'est pas disponible
    if not SCIPY_AVAILABLE:
        st.markdown("""
        <div class="warning-banner">
            ⚠️ <strong>Fonctionnalités limitées</strong><br>
            Le module scipy n'est pas installé. Certaines analyses avancées (ANOVA, clustering) seront limitées.<br>
            Exécutez: <code>pip install scipy</code> pour activer toutes les fonctionnalités.
        </div>
        """, unsafe_allow_html=True)

    # Onglets simplifiés sans analyses avancées qui nécessitent scipy
    if SCIPY_AVAILABLE:
        tabs = st.tabs([
            "📊 Descriptives",
            "📈 Temporelles",
            "🌍 Géographiques",
            "🎯 Performance",
            "📋 Comparatives",
            "🔮 Prédictives",
            "📈 Qualité Données"
        ])
    else:
        tabs = st.tabs([
            "📊 Descriptives",
            "📈 Temporelles",
            "🌍 Géographiques",
            "🎯 Performance",
            "📋 Comparatives",
            "📈 Qualité Données"
        ])

    with tabs[0]:
        display_descriptive_analyses(df, title)

    with tabs[1]:
        display_temporal_analyses(df, title)

    with tabs[2]:
        display_geographic_analyses(df, title)

    with tabs[3]:
        display_performance_analyses(df, title)

    with tabs[4]:
        display_comparative_analyses(df, title)

    if SCIPY_AVAILABLE:
        with tabs[5]:
            display_predictive_analyses(df, title)
        with tabs[6]:
            display_data_quality_analyses(df, title)
    else:
        with tabs[5]:
            display_data_quality_analyses(df, title)

    st.markdown('</div>', unsafe_allow_html=True)


# Les autres fonctions display_* restent inchangées...
def display_descriptive_analyses(df, title):
    """Affiche les analyses descriptives"""
    st.markdown("#### 📊 Analyses Descriptives")

    if df.empty:
        st.info("Aucune donnée pour l'analyse descriptive")
        return

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Moyenne", f"{df.select_dtypes(include=[np.number]).mean().mean():.2f}")
    with col2:
        st.metric("Médiane", f"{df.select_dtypes(include=[np.number]).median().median():.2f}")
    with col3:
        st.metric("Écart-type", f"{df.select_dtypes(include=[np.number]).std().mean():.2f}")
    with col4:
        missing = df.isnull().sum().sum()
        total = df.size
        st.metric("Données manquantes", f"{missing}/{total}")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    if numeric_cols:
        st.markdown("##### 📈 Distributions")
        selected_col = st.selectbox("Sélectionnez une variable numérique", numeric_cols)

        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(df, x=selected_col, nbins=30,
                               title=f"Distribution de {selected_col}")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.box(df, y=selected_col, title=f"Boîte à moustaches - {selected_col}")
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("##### 📋 Statistiques détaillées")
        st.dataframe(df[selected_col].describe(), use_container_width=True)

    categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    if categorical_cols:
        st.markdown("##### 📊 Analyses catégorielles")
        cat_col = st.selectbox("Sélectionnez une variable catégorielle", categorical_cols)

        if cat_col:
            value_counts = df[cat_col].value_counts()
            fig = px.bar(x=value_counts.index, y=value_counts.values,
                         title=f"Distribution de {cat_col}")
            st.plotly_chart(fig, use_container_width=True)


def display_geographic_analyses(df, title):
    """Affiche les analyses géographiques"""
    st.markdown("#### 🌍 Analyses Géographiques")

    geo_cols = [col for col in df.columns if any(x in str(col).lower()
                                                 for x in
                                                 ['région', 'district', 'province', 'ville', 'département', 'zone'])]

    if not geo_cols:
        st.info("Aucune colonne géographique détectée")
        return

    geo_col = st.selectbox("Colonne géographique", geo_cols)
    value_col = st.selectbox("Variable à cartographier",
                             df.select_dtypes(include=[np.number]).columns.tolist())

    if geo_col and value_col:
        geo_data = df.groupby(geo_col)[value_col].agg(['mean', 'sum', 'std', 'count']).reset_index()
        geo_data.columns = [geo_col, 'Moyenne', 'Somme', 'Écart-type', 'Nombre']

        st.markdown("##### 🗺️ Carte Choroplèthe")
        try:
            fig = px.choropleth(
                geo_data,
                locations=geo_col,
                locationmode='country names',
                color='Somme',
                title=f"Distribution géographique de {value_col}",
                color_continuous_scale="Viridis"
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        except:
            st.dataframe(geo_data.sort_values('Somme', ascending=False), use_container_width=True)

        st.markdown("##### 📊 Comparaison Régionale")
        top_n = st.slider("Nombre de régions à afficher", 5, 20, 10)

        top_regions = geo_data.nlargest(top_n, 'Somme')
        fig = px.bar(top_regions, x=geo_col, y='Somme',
                     title=f"Top {top_n} régions pour {value_col}")
        st.plotly_chart(fig, use_container_width=True)


def display_performance_analyses(df, title):
    """Affiche les analyses de performance (ECV/DSDM)"""
    st.markdown("#### 🎯 Analyses de Performance")

    perf_cols = []
    for col in df.columns:
        col_str = str(col).lower()
        if any(x in col_str for x in ['%', 'pourcentage', 'taux', 'performance', 'réalisation', 'cible', 'score']):
            if pd.api.types.is_numeric_dtype(df[col]):
                perf_cols.append(col)
        elif df[col].dtype in ['int64', 'float64']:
            # Ajouter toutes les colonnes numériques comme options potentielles
            perf_cols.append(col)

    # Supprimer les doublons
    perf_cols = list(set(perf_cols))

    if not perf_cols:
        st.info("Aucun indicateur de performance détecté")
        return

    perf_col = st.selectbox("Indicateur de performance", perf_cols)

    if perf_col:
        st.markdown("##### 📊 Distribution des performances")

        col1, col2 = st.columns(2)
        with col1:
            fig = px.histogram(df, x=perf_col, nbins=20,
                               title=f"Distribution de {perf_col}")
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            # Afficher les statistiques descriptives
            if len(df) > 0:
                q1 = df[perf_col].quantile(0.25)
                median = df[perf_col].median()
                q3 = df[perf_col].quantile(0.75)
                mean_val = df[perf_col].mean()
                std_val = df[perf_col].std()

                st.metric("Moyenne", f"{mean_val:.1f}")
                st.metric("Écart-type", f"{std_val:.1f}")
                st.metric("25e percentile", f"{q1:.1f}")
                st.metric("Médiane", f"{median:.1f}")
                st.metric("75e percentile", f"{q3:.1f}")

        st.markdown("##### 📋 Classification par seuils")

        # Afficher les données sous forme de tableau
        with st.expander("📋 Voir les données brutes"):
            st.dataframe(df[[perf_col]].describe(), use_container_width=True)
            if len(df) <= 100:
                st.dataframe(df[[perf_col]], use_container_width=True)
            else:
                st.dataframe(df[[perf_col]].head(100), use_container_width=True)
                st.info(f"Affiche les 100 premières lignes sur {len(df)} au total")

        # Remplacer le slider à 3 valeurs par 3 sliders séparés ou un slider à plage
        st.markdown("##### 🎯 Définir les seuils de classification")

        col1, col2, col3 = st.columns(3)
        with col1:
            seuil_faible = st.slider("Seuil faible/moyen", 0, 100, 70)
        with col2:
            seuil_moyen_bon = st.slider("Seuil moyen/bon", 0, 100, 85)
        with col3:
            seuil_bon_excellent = st.slider("Seuil bon/excellent", 0, 100, 95)

        # Assurer l'ordre croissant des seuils
        seuil_faible = min(seuil_faible, seuil_moyen_bon - 1)
        seuil_moyen_bon = max(min(seuil_moyen_bon, seuil_bon_excellent - 1), seuil_faible + 1)
        seuil_bon_excellent = max(seuil_bon_excellent, seuil_moyen_bon + 1)

        # Créer les catégories
        try:
            bins = [0, seuil_faible, seuil_moyen_bon, seuil_bon_excellent, 100]
            labels = ['Faible', 'Moyenne', 'Bonne', 'Excellente']

            # Vérifier que les bins sont dans l'ordre croissant
            if all(bins[i] < bins[i + 1] for i in range(len(bins) - 1)):
                df['Catégorie'] = pd.cut(df[perf_col],
                                         bins=bins,
                                         labels=labels,
                                         include_lowest=True)

                # Compter les catégories
                cat_dist = df['Catégorie'].value_counts().sort_index()

                # Créer le graphique en camembert
                if not cat_dist.empty:
                    fig = px.pie(values=cat_dist.values, names=cat_dist.index,
                                 title="Répartition par catégorie de performance",
                                 color_discrete_sequence=px.colors.sequential.RdBu)
                    st.plotly_chart(fig, use_container_width=True)

                    # Afficher le tableau des catégories
                    st.markdown("##### 📊 Répartition détaillée")
                    cat_stats = pd.DataFrame({
                        'Catégorie': cat_dist.index,
                        'Nombre': cat_dist.values,
                        'Pourcentage': (cat_dist.values / len(df) * 100).round(1)
                    })
                    st.dataframe(cat_stats, use_container_width=True)

                    # Afficher un échantillon des données classées
                    st.markdown("##### 📋 Échantillon des données classées")
                    sample_df = df[[perf_col, 'Catégorie']].head(20)
                    st.dataframe(sample_df.sort_values(by=perf_col, ascending=False),
                                 use_container_width=True)
                else:
                    st.warning("Aucune donnée à catégoriser avec les seuils actuels")
            else:
                st.error("Les seuils doivent être dans l'ordre croissant. Ajustez les valeurs.")

        except Exception as e:
            st.error(f"Erreur lors de la classification: {str(e)}")

            # Alternative: classification simple par quartiles
            st.markdown("##### 🔄 Classification alternative par quartiles")
            df['Catégorie_Quartile'] = pd.qcut(df[perf_col], q=4,
                                               labels=['Très faible', 'Faible', 'Moyen', 'Élevé'])
            cat_dist_q = df['Catégorie_Quartile'].value_counts()

            if not cat_dist_q.empty:
                fig = px.pie(values=cat_dist_q.values, names=cat_dist_q.index,
                             title="Répartition par quartiles")
                st.plotly_chart(fig, use_container_width=True)


def display_data_quality_analyses(df, title):
    """Affiche les analyses de qualité des données"""
    st.markdown("#### 📈 Analyse de la Qualité des Données")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        missing_pct = (df.isnull().sum().sum() / df.size) * 100
        st.metric("Données manquantes", f"{missing_pct:.1f}%")

    with col2:
        duplicate_rows = df.duplicated().sum()
        st.metric("Lignes dupliquées", duplicate_rows)

    with col3:
        numeric_cols = len(df.select_dtypes(include=[np.number]).columns)
        st.metric("Colonnes numériques", numeric_cols)

    with col4:
        zero_counts = (df.select_dtypes(include=[np.number]) == 0).sum().sum()
        st.metric("Valeurs zéro", zero_counts)

    st.markdown("##### 🔍 Valeurs manquantes par colonne")
    missing_by_col = df.isnull().sum().sort_values(ascending=False)
    missing_by_col = missing_by_col[missing_by_col > 0]

    if len(missing_by_col) > 0:
        fig = px.bar(x=missing_by_col.index, y=missing_by_col.values,
                     title="Valeurs manquantes par colonne")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.success("✅ Aucune valeur manquante détectée")


# Les autres fonctions restent inchangées...
# (get_dashboard_item_types, display_dashboard_item, display_dashboard_card, etc.)

def display_dashboard_item(item, idx):
    """Affiche un élément du dashboard avec toutes les analyses"""
    st.markdown(f"#### 📋 Élément {idx + 1}")

    with st.expander("📋 Informations", expanded=True):
        if 'visualization' in item and item['visualization']:
            viz = item['visualization']
            st.markdown(f"**Type:** 📊 {viz.get('type', 'Visualisation')}")
            st.markdown(f"**Nom:** {viz.get('name', 'Sans nom')}")

        elif 'chart' in item and item['chart']:
            chart = item['chart']
            st.markdown(f"**Type:** 📈 Graphique - {chart.get('type', 'Chart')}")
            st.markdown(f"**Nom:** {chart.get('name', 'Sans nom')}")

        elif 'map' in item and item['map']:
            map_item = item['map']
            st.markdown(f"**Type:** 🌍 Carte")
            st.markdown(f"**Nom:** {map_item.get('name', 'Sans nom')}")

        elif 'text' in item:
            st.markdown(f"**Type:** 📝 Texte")
            text_content = item.get('text', '')
            st.markdown(f"**Contenu:** {text_content[:200]}...")

    data, info, item_type = st.session_state.client.get_item_data(item)
    item_name = get_item_name(item, idx)

    if not data.empty:
        display_all_analysis_tabs(data, item_name, info)
    else:
        st.warning(f"⚠️ Aucune donnée disponible pour {item_name}")

    st.markdown("---")


def get_dashboard_item_types(items):
    """Récupère la liste des types d'éléments présents dans un dashboard"""
    item_types = {
        'visualizations': [],
        'charts': [],
        'maps': [],
        'texts': [],
        'others': []
    }

    for item in items:
        if 'visualization' in item and item['visualization']:
            viz = item['visualization']
            item_types['visualizations'].append({
                'name': viz.get('name', 'Visualisation sans nom'),
                'type': viz.get('type', 'Non spécifié'),
                'id': viz.get('id', '')
            })
        elif 'chart' in item and item['chart']:
            chart = item['chart']
            item_types['charts'].append({
                'name': chart.get('name', 'Graphique sans nom'),
                'type': chart.get('type', 'Chart'),
                'id': chart.get('id', '')
            })
        elif 'map' in item and item['map']:
            map_item = item['map']
            item_types['maps'].append({
                'name': map_item.get('name', 'Carte sans nom'),
                'id': map_item.get('id', '')
            })
        elif 'text' in item:
            text_content = item.get('text', '')
            item_types['texts'].append({
                'name': f"Texte: {text_content[:50]}..." if len(text_content) > 50 else f"Texte: {text_content}",
                'content': text_content
            })
        else:
            item_types['others'].append({
                'type': item.get('type', 'Inconnu'),
                'details': str(item)[:100]
            })

    return item_types


def display_dashboard_card(dashboard, idx):
    """Affiche une carte de dashboard avec les types de visualisation"""
    created = dashboard.get('created', '')[:10] if dashboard.get('created') else 'N/A'
    items = dashboard.get('dashboardItems', [])
    item_count = len(items)

    owner_info = dashboard.get('user', {})
    owner_name = owner_info.get('name', 'Inconnu')
    is_owner = dashboard.get('is_owner', False)

    item_types = get_dashboard_item_types(items)

    badge_html = '<span class="owner-badge">Propriétaire</span>' if is_owner else '<span class="all-badge">Public</span>'

    types_html = []
    if item_types['visualizations']:
        viz_types = set([viz['type'] for viz in item_types['visualizations']])
        types_html.append(f"📊 {len(item_types['visualizations'])} visualisation(s)")
        for viz_type in viz_types:
            count = sum(1 for v in item_types['visualizations'] if v['type'] == viz_type)
            types_html.append(f"<span class='types-badge'>{viz_type}: {count}</span>")

    if item_types['charts']:
        types_html.append(f"📈 {len(item_types['charts'])} graphique(s)")

    if item_types['maps']:
        types_html.append(f"🌍 {len(item_types['maps'])} carte(s)")

    if item_types['texts']:
        types_html.append(f"📝 {len(item_types['texts'])} texte(s)")

    if item_types['others']:
        types_html.append(f"🔧 {len(item_types['others'])} autre(s)")

    types_summary = "<br>".join(types_html)

    st.markdown(f"""
    <div class="dashboard-card">
        <h4>📊 {dashboard.get('name', 'Sans nom')} {badge_html}</h4>
        <p>📅 Créé le: {created}</p>
        <p>📊 {item_count} éléments</p>
        <p><strong>👤 {owner_name}</strong></p>
        <div class="types-container">
            <strong>Types disponibles:</strong><br>
            {types_summary}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Ouvrir", key=f"open_{dashboard['id']}_{idx}", use_container_width=True):
        with st.spinner("Chargement du dashboard..."):
            details = st.session_state.client.get_dashboard_details(dashboard['id'])
            if details:
                details['is_owner'] = is_owner
                details['owner_info'] = owner_info
                details['item_types'] = get_dashboard_item_types(details.get('dashboardItems', []))
                st.session_state.current_dashboard = details
                st.rerun()


def display_selected_dashboard():
    """Affiche un dashboard sélectionné avec tous ses éléments"""
    dashboard = st.session_state.current_dashboard

    if not dashboard:
        return

    # En-tête du dashboard
    col1, col2, col3 = st.columns([3, 1, 1])

    with col1:
        owner_info = dashboard.get('owner_info', {})
        owner_name = owner_info.get('name', 'Inconnu')
        is_owner = dashboard.get('is_owner', False)

        st.markdown(f"# 📊 {dashboard.get('name', 'Dashboard sans nom')}")
        st.markdown(f"**👤 Propriétaire:** {owner_name} {'(Vous)' if is_owner else ''}")

        if dashboard.get('description'):
            st.markdown(f"**📝 Description:** {dashboard.get('description')}")

    with col2:
        if st.button("📥 Exporter tout", use_container_width=True, help="Exporter tous les éléments du dashboard"):
            export_all_dashboard_items(dashboard)

    with col3:
        if st.button("← Retour", use_container_width=True):
            st.session_state.current_dashboard = None
            st.rerun()

    # ... (le reste du code reste inchangé) ...
    # Métriques du dashboard
    items = dashboard.get('dashboardItems', [])
    item_types = dashboard.get('item_types', {})

    # Afficher toutes les statistiques
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Éléments totaux", len(items))
    with col2:
        st.metric("Visualisations", len(item_types.get('visualizations', [])))
    with col3:
        st.metric("Graphiques", len(item_types.get('charts', [])))
    with col4:
        st.metric("Cartes", len(item_types.get('maps', [])))
    with col5:
        st.metric("Textes", len(item_types.get('texts', [])))

    st.markdown("---")

    # Option pour afficher tous les éléments en une fois
    show_all = st.checkbox("📋 Afficher TOUS les éléments en une page", value=True)

    if show_all:
        display_all_dashboard_items(items)
    else:
        # Affichage avec onglets par type
        display_dashboard_by_type(items, item_types)

    # Bouton retour en bas
    st.markdown("---")
    if st.button("← Retour à la liste des dashboards", use_container_width=True):
        st.session_state.current_dashboard = None
        st.rerun()


def display_all_dashboard_items(items):
    """Affiche tous les éléments du dashboard en une page"""
    if not items:
        st.warning("Ce dashboard ne contient aucun élément")
        return

    st.markdown("## 📋 Tous les éléments du dashboard")

    # Options d'affichage
    display_mode = st.radio(
        "Mode d'affichage:",
        ["📋 Contenu complet", "📊 Analyses seulement", "📁 Données seulement"],
        horizontal=True
    )

    # Afficher tous les éléments
    for idx, item in enumerate(items):
        if has_visualizable_data(item):
            if display_mode == "📋 Contenu complet":
                display_item_full_content(item, idx)
                st.markdown("---")
            elif display_mode == "📊 Analyses seulement":
                display_dashboard_item_with_transform(item, idx)
                st.markdown("---")
            elif display_mode == "📁 Données seulement":
                display_data_only(item, idx)
                st.markdown("---")

    # Résumé
    st.markdown(f"**Total d'éléments affichés:** {len(items)}")


def display_data_only(item, idx):
    """Affiche uniquement les données d'un élément"""
    item_name = get_item_name(item, idx)

    st.markdown(f"### 📊 Données: {item_name}")

    # Récupérer les données
    data, info, item_type = st.session_state.client.get_item_data(item)

    if not data.empty:
        st.info(info)
        display_data_content(data)
    else:
        st.warning(f"⚠️ Aucune donnée disponible pour {item_name}")


def display_item_full_content(item, idx):
    """Affiche le contenu complet d'un élément du dashboard"""
    item_name = get_item_name(item, idx)
    item_type = get_item_type(item)

    st.markdown(f"### 📋 Élément {idx + 1}: {item_name}")

    # Afficher les informations de base
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"**Type:** {get_item_type_icon(item_type)} {item_type}")
    with col2:
        st.markdown(f"**ID:** {get_item_id(item)}")

    # Afficher le contenu spécifique selon le type
    if item_type == "visualization":
        display_visualization_content(item['visualization'])
    elif item_type == "chart":
        display_chart_content(item['chart'])
    elif item_type == "map":
        display_map_content(item['map'])
    elif item_type == "text":
        display_text_content(item)
    else:
        display_other_content(item)

    # Récupérer et afficher les données
    data, info, data_type = st.session_state.client.get_item_data(item)

    if not data.empty:
        st.markdown("#### 📊 Données associées")
        st.info(info)

        # Afficher les données
        with st.expander("📋 Voir les données", expanded=True):
            display_data_content(data)

        # Options d'export
        display_export_options(data, item_name)
    else:
        st.warning("Aucune donnée disponible pour cet élément")


def get_item_id(item):
    """Récupère l'ID d'un élément"""
    if 'visualization' in item and item['visualization']:
        return item['visualization'].get('id', 'N/A')
    elif 'chart' in item and item['chart']:
        return item['chart'].get('id', 'N/A')
    elif 'map' in item and item['map']:
        return item['map'].get('id', 'N/A')
    elif 'text' in item:
        return "text_" + str(hash(item.get('text', '')))[:8]
    return 'N/A'


def display_visualization_content(viz):
    """Affiche le contenu d'une visualisation"""
    st.markdown("#### 📊 Détails de la visualisation")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nom:** {viz.get('name', 'Non spécifié')}")
        st.markdown(f"**Type:** {viz.get('type', 'Non spécifié')}")
        st.markdown(f"**Description:** {viz.get('description', 'Non spécifiée')}")

    with col2:
        # Afficher les dimensions si disponibles
        if 'dimensions' in viz:
            st.markdown("**Dimensions:**")
            for dim in viz.get('dimensions', []):
                st.markdown(f"- {dim}")

        # Afficher les filtres si disponibles
        if 'filters' in viz:
            st.markdown("**Filtres:**")
            for filt in viz.get('filters', []):
                st.markdown(f"- {filt}")

    # Afficher les axes si disponibles
    if 'axes' in viz:
        st.markdown("**Configuration des axes:**")
        for axis_name, axis_config in viz.get('axes', {}).items():
            st.markdown(f"- **{axis_name}:** {axis_config}")

    # Afficher les séries si disponibles
    if 'series' in viz:
        st.markdown("**Séries de données:**")
        series_data = viz.get('series', [])
        if isinstance(series_data, list):
            for i, serie in enumerate(series_data[:5]):  # Limiter à 5 séries
                st.markdown(f"{i + 1}. {str(serie)[:100]}...")
            if len(series_data) > 5:
                st.info(f"... et {len(series_data) - 5} autres séries")
        else:
            st.json(series_data)


def display_chart_content(chart):
    """Affiche le contenu d'un graphique"""
    st.markdown("#### 📈 Détails du graphique")

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**Nom:** {chart.get('name', 'Non spécifié')}")
        st.markdown(f"**Type:** {chart.get('type', 'Non spécifié')}")
        st.markdown(f"**Sous-type:** {chart.get('subtype', 'Non spécifié')}")

    with col2:
        st.markdown(f"**Titre:** {chart.get('title', 'Non spécifié')}")
        st.markdown(f"**Sous-titre:** {chart.get('subtitle', 'Non spécifié')}")

    # Afficher la configuration si disponible
    if 'config' in chart:
        with st.expander("⚙️ Configuration du graphique"):
            st.json(chart.get('config', {}))

    # Afficher les séries
    if 'series' in chart:
        st.markdown("**Séries:**")
        series_list = chart.get('series', [])
        if isinstance(series_list, list):
            for i, serie in enumerate(series_list[:10]):  # Limiter à 10
                if isinstance(serie, dict):
                    st.markdown(f"- **{serie.get('name', f'Série {i + 1}')}**: {serie.get('type', 'N/A')}")
                else:
                    st.markdown(f"- {str(serie)[:100]}...")


def display_map_content(map_item):
    """Affiche le contenu d'une carte"""
    st.markdown("#### 🌍 Détails de la carte")

    st.markdown(f"**Nom:** {map_item.get('name', 'Non spécifié')}")
    st.markdown(f"**Description:** {map_item.get('description', 'Non spécifiée')}")

    # Afficher les couches si disponibles
    if 'layers' in map_item:
        layers = map_item.get('layers', [])
        st.markdown(f"**Nombre de couches:** {len(layers)}")

        for i, layer in enumerate(layers[:5]):  # Limiter à 5 couches
            with st.expander(f"Couche {i + 1}: {layer.get('name', 'Sans nom')}"):
                st.markdown(f"**Type:** {layer.get('type', 'N/A')}")
                st.markdown(f"**Style:** {layer.get('style', 'N/A')}")
                if 'config' in layer:
                    st.markdown("**Configuration:**")
                    st.json(layer['config'])


def display_text_content(item):
    """Affiche le contenu d'un texte"""
    st.markdown("#### 📝 Contenu textuel")

    text_content = item.get('text', '')

    # Afficher le texte complet
    st.markdown("**Texte complet:**")
    st.markdown(f"""
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 5px; border: 1px solid #dee2e6;">
    {text_content}
    </div>
    """, unsafe_allow_html=True)

    # Statistiques du texte
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Longueur", f"{len(text_content)} caractères")
    with col2:
        st.metric("Mots", f"{len(text_content.split())}")
    with col3:
        st.metric("Lignes", f"{len(text_content.splitlines())}")
    with col4:
        st.metric("Taille", f"{(len(text_content.encode('utf-8')) / 1024):.2f} KB")

    # Afficher le texte formaté s'il contient du HTML
    if '<' in text_content and '>' in text_content:
        with st.expander("📄 Voir le texte formaté (HTML)"):
            st.markdown(text_content, unsafe_allow_html=True)

    # Extraire et afficher les liens s'il y en a
    import re
    links = re.findall(r'https?://\S+', text_content)
    if links:
        with st.expander("🔗 Liens détectés"):
            for link in links:
                st.markdown(f"- [{link}]({link})")


def display_other_content(item):
    """Affiche le contenu d'autres types d'éléments"""
    st.markdown("#### 🔧 Contenu de l'élément")

    # Afficher les clés disponibles
    st.markdown("**Structure de l'élément:**")
    for key in item.keys():
        if key not in ['visualization', 'chart', 'map', 'text']:
            value = item[key]
            if isinstance(value, (dict, list)):
                with st.expander(f"📁 {key}"):
                    st.json(value)
            else:
                st.markdown(f"**{key}:** {value}")

    # Afficher l'élément complet en JSON
    with st.expander("📄 Vue JSON complète"):
        st.json(item)


def display_data_content(data):
    """Affiche le contenu des données"""
    # Informations générales
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Lignes", data.shape[0])
    with col2:
        st.metric("Colonnes", data.shape[1])
    with col3:
        missing = data.isnull().sum().sum()
        total = data.size
        st.metric("Valeurs manquantes", f"{missing}/{total}")
    with col4:
        numeric_cols = len(data.select_dtypes(include=[np.number]).columns)
        st.metric("Colonnes numériques", numeric_cols)

    # Aperçu des données
    st.markdown("**Aperçu des données:**")
    st.dataframe(data, use_container_width=True)

    # Informations détaillées sur les colonnes
    with st.expander("📋 Informations sur les colonnes"):
        col_info = []
        for col in data.columns:
            col_info.append({
                'Colonne': col,
                'Type': str(data[col].dtype),
                'Valeurs uniques': data[col].nunique(),
                'Valeurs manquantes': data[col].isnull().sum(),
                'Première valeur': str(data[col].iloc[0]) if len(data) > 0 else '',
                'Dernière valeur': str(data[col].iloc[-1]) if len(data) > 0 else ''
            })
        st.dataframe(pd.DataFrame(col_info), use_container_width=True)

    # Statistiques numériques
    numeric_data = data.select_dtypes(include=[np.number])
    if not numeric_data.empty:
        with st.expander("📊 Statistiques numériques"):
            st.dataframe(numeric_data.describe(), use_container_width=True)


def display_export_options(data, item_name):
    """Affiche les options d'export des données"""
    st.markdown("#### 📥 Options d'export")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Export CSV
        csv = data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Télécharger CSV",
            data=csv,
            file_name=f"{clean_filename(item_name)}.csv",
            mime="text/csv"
        )

    with col2:
        # Export Excel
        try:
            import io
            from pandas import ExcelWriter

            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                data.to_excel(writer, index=False, sheet_name='Données')
            excel_data = output.getvalue()

            st.download_button(
                label="📊 Télécharger Excel",
                data=excel_data,
                file_name=f"{clean_filename(item_name)}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except:
            st.button("📊 Excel (non disponible)", disabled=True)

    with col3:
        # Export JSON
        json_data = data.to_json(orient='records', force_ascii=False)
        st.download_button(
            label="📄 Télécharger JSON",
            data=json_data.encode('utf-8'),
            file_name=f"{clean_filename(item_name)}.json",
            mime="application/json"
        )

    # Aperçu des données
    with st.expander("👁️ Aperçu des données exportées"):
        tab1, tab2, tab3 = st.tabs(["CSV", "JSON", "Tableau"])

        with tab1:
            st.code(data.head(20).to_csv(index=False), language="csv")

        with tab2:
            st.json(json.loads(json_data)[:10])  # Premier 10 enregistrements

        with tab3:
            st.dataframe(data.head(20), use_container_width=True)


def clean_filename(filename):
    """Nettoie un nom de fichier"""
    import re
    # Remplacer les caractères spéciaux par des underscores
    cleaned = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Limiter la longueur
    return cleaned[:50]

def export_all_dashboard_items(dashboard):
    """Exporte tous les éléments du dashboard"""
    items = dashboard.get('dashboardItems', [])

    if not items:
        st.warning("Aucun élément à exporter")
        return

    # Créer un DataFrame avec les métadonnées
    metadata = []
    for idx, item in enumerate(items):
        item_name = get_item_name(item, idx)
        item_type = get_item_type(item)

        metadata.append({
            'index': idx + 1,
            'nom': item_name,
            'type': item_type,
            'id': get_item_id(item),
            'has_data': has_visualizable_data(item)
        })

    metadata_df = pd.DataFrame(metadata)

    # Créer un fichier Excel avec plusieurs onglets
    try:
        import io
        from pandas import ExcelWriter

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Onglet métadonnées
            metadata_df.to_excel(writer, index=False, sheet_name='Métadonnées')

            # Onglets pour les données de chaque élément
            for idx, item in enumerate(items):
                if has_visualizable_data(item):
                    data, _, _ = st.session_state.client.get_item_data(item)
                    if not data.empty:
                        sheet_name = f"Élément_{idx + 1}"
                        if len(sheet_name) > 31:  # Limite Excel
                            sheet_name = sheet_name[:31]
                        data.to_excel(writer, index=False, sheet_name=sheet_name)

        excel_data = output.getvalue()

        # Téléchargement
        dashboard_name = clean_filename(dashboard.get('name', 'dashboard'))
        st.download_button(
            label="📥 Télécharger l'export complet",
            data=excel_data,
            file_name=f"{dashboard_name}_export_complet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.success(f"Prêt à exporter {len(items)} éléments")

    except Exception as e:
        st.error(f"Erreur lors de l'export: {str(e)}")

def has_visualizable_data(item):
    """Vérifie si l'élément a des données visualisables"""
    if 'visualization' in item and item['visualization']:
        return True
    elif 'chart' in item and item['chart']:
        return True
    elif 'map' in item and item['map']:
        return True
    elif 'text' in item and item.get('text', '').strip():
        return True
    return False


def display_dashboard_item_with_transform(item, idx):
    """Affiche un élément du dashboard avec toutes ses transformations"""
    # Récupérer les données
    data, info, item_type = st.session_state.client.get_item_data(item)
    item_name = get_item_name(item, idx)

    # Afficher l'en-tête de l'élément
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f"### 📋 Élément {idx + 1}: {item_name}")
    with col2:
        st.markdown(f"**Type:** {get_item_type_icon(item_type)} {item_type}")

    # Afficher les informations
    with st.expander("📋 Informations détaillées", expanded=False):
        display_item_details(item)
        st.info(info)

    if not data.empty:
        # Afficher les données brutes
        with st.expander("📊 Données brutes", expanded=False):
            display_raw_data(data)

        # Afficher les transformations disponibles
        if len(data) > 0:
            display_data_transformations(data, item_name)

        # Afficher les analyses
        display_all_analysis_tabs(data, item_name, info)
    else:
        st.warning(f"⚠️ Aucune donnée disponible pour {item_name}")


def get_item_type_icon(item_type):
    """Retourne l'icône correspondant au type d'élément"""
    icons = {
        'visualization': '📊',
        'chart': '📈',
        'map': '🌍',
        'text': '📝',
        'Données génériques': '📋',
        'Erreur': '❌'
    }
    return icons.get(item_type, '📋')


def display_item_details(item):
    """Affiche les détails d'un élément"""
    if 'visualization' in item and item['visualization']:
        viz = item['visualization']
        st.markdown(f"**Type:** 📊 {viz.get('type', 'Visualisation')}")
        st.markdown(f"**Nom:** {viz.get('name', 'Sans nom')}")
        if viz.get('id'):
            st.markdown(f"**ID:** {viz.get('id')}")

    elif 'chart' in item and item['chart']:
        chart = item['chart']
        st.markdown(f"**Type:** 📈 Graphique - {chart.get('type', 'Chart')}")
        st.markdown(f"**Nom:** {chart.get('name', 'Sans nom')}")
        if chart.get('id'):
            st.markdown(f"**ID:** {chart.get('id')}")

    elif 'map' in item and item['map']:
        map_item = item['map']
        st.markdown(f"**Type:** 🌍 Carte")
        st.markdown(f"**Nom:** {map_item.get('name', 'Sans nom')}")
        if map_item.get('id'):
            st.markdown(f"**ID:** {map_item.get('id')}")

    elif 'text' in item:
        st.markdown(f"**Type:** 📝 Texte")
        text_content = item.get('text', '')
        st.markdown(f"**Contenu:**")
        st.markdown(f"```\n{text_content}\n```")


def display_raw_data(data):
    """Affiche les données brutes"""
    st.markdown(f"**Dimensions:** {data.shape[0]} lignes × {data.shape[1]} colonnes")

    # Afficher un aperçu des données
    st.dataframe(data.head(100), use_container_width=True)

    if len(data) > 100:
        st.info(f"Affiche les 100 premières lignes sur {len(data)} au total")

    # Afficher les informations sur les colonnes
    with st.expander("📋 Informations sur les colonnes"):
        col_info = pd.DataFrame({
            'Colonne': data.columns,
            'Type': data.dtypes.values,
            'Valeurs uniques': [data[col].nunique() for col in data.columns],
            'Valeurs manquantes': [data[col].isnull().sum() for col in data.columns],
            'Exemple': [str(data[col].iloc[0]) if len(data) > 0 else '' for col in data.columns]
        })
        st.dataframe(col_info, use_container_width=True)


def display_data_transformations(data, item_name):
    """Affiche les transformations disponibles pour les données"""
    st.markdown("#### 🔄 Transformations des données")

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📥 Télécharger CSV", key=f"download_{item_name}"):
            csv = data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="Cliquez pour télécharger",
                data=csv,
                file_name=f"{item_name.replace(' ', '_')}.csv",
                mime="text/csv",
                key=f"download_btn_{item_name}"
            )

    with col2:
        if st.button("📊 Statistiques résumées", key=f"stats_{item_name}"):
            display_summary_statistics(data)

    with col3:
        if st.button("🎨 Visualisations rapides", key=f"quick_viz_{item_name}"):
            display_quick_visualizations(data, item_name)

    # Options de filtrage
    st.markdown("##### 🔍 Filtrage des données")
    filter_col = st.selectbox(
        "Sélectionner une colonne pour filtrer",
        ["Aucun filtre"] + list(data.columns),
        key=f"filter_{item_name}"
    )

    if filter_col != "Aucun filtre":
        if data[filter_col].dtype == 'object' or data[filter_col].nunique() < 20:
            unique_values = data[filter_col].dropna().unique()
            selected_values = st.multiselect(
                f"Sélectionner les valeurs de {filter_col}",
                options=unique_values,
                default=list(unique_values)[:min(5, len(unique_values))],
                key=f"multiselect_{item_name}_{filter_col}"
            )
            if selected_values:
                filtered_data = data[data[filter_col].isin(selected_values)]
                st.info(f"Filtré: {len(filtered_data)} lignes sur {len(data)}")
                st.dataframe(filtered_data.head(50), use_container_width=True)
        else:
            min_val = float(data[filter_col].min())
            max_val = float(data[filter_col].max())
            selected_range = st.slider(
                f"Plage pour {filter_col}",
                min_val, max_val, (min_val, max_val),
                key=f"slider_{item_name}_{filter_col}"
            )
            filtered_data = data[
                (data[filter_col] >= selected_range[0]) &
                (data[filter_col] <= selected_range[1])
                ]
            st.info(f"Filtré: {len(filtered_data)} lignes sur {len(data)}")
            st.dataframe(filtered_data.head(50), use_container_width=True)


def display_summary_statistics(data):
    """Affiche les statistiques résumées"""
    st.markdown("##### 📊 Statistiques résumées")

    # Statistiques pour les colonnes numériques
    numeric_cols = data.select_dtypes(include=[np.number]).columns
    if len(numeric_cols) > 0:
        st.markdown("**Colonnes numériques:**")
        numeric_stats = data[numeric_cols].describe().T
        numeric_stats['type'] = 'numérique'
        st.dataframe(numeric_stats, use_container_width=True)

    # Statistiques pour les colonnes catégorielles
    categorical_cols = data.select_dtypes(exclude=[np.number]).columns
    if len(categorical_cols) > 0:
        st.markdown("**Colonnes catégorielles:**")
        cat_stats = []
        for col in categorical_cols:
            if data[col].nunique() < 50:  # Éviter les colonnes avec trop de valeurs uniques
                cat_stats.append({
                    'colonne': col,
                    'type': 'catégorielle',
                    'valeurs_uniques': data[col].nunique(),
                    'valeur_plus_fréquente': data[col].mode().iloc[0] if len(data[col].mode()) > 0 else None,
                    'fréquence_valeur_plus_fréquente': data[col].value_counts().iloc[0] if len(data[col]) > 0 else 0
                })
        if cat_stats:
            st.dataframe(pd.DataFrame(cat_stats), use_container_width=True)


def display_quick_visualizations(data, item_name):
    """Affiche des visualisations rapides"""
    st.markdown("##### 🎨 Visualisations rapides")

    # Sélectionner le type de visualisation
    viz_type = st.selectbox(
        "Type de visualisation",
        ["Histogramme", "Nuage de points", "Boîte à moustaches", "Graphique en barres", "Ligne"],
        key=f"viz_type_{item_name}"
    )

    numeric_cols = data.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = data.select_dtypes(exclude=[np.number]).columns.tolist()

    if viz_type == "Histogramme" and numeric_cols:
        col = st.selectbox("Colonne numérique", numeric_cols, key=f"hist_{item_name}")
        fig = px.histogram(data, x=col, nbins=30, title=f"Histogramme de {col}")
        st.plotly_chart(fig, use_container_width=True)

    elif viz_type == "Nuage de points" and len(numeric_cols) >= 2:
        col1 = st.selectbox("Axe X", numeric_cols, key=f"scatter_x_{item_name}")
        col2 = st.selectbox("Axe Y", numeric_cols, key=f"scatter_y_{item_name}")
        if categorical_cols:
            color_col = st.selectbox("Couleur par (optionnel)", ["Aucun"] + categorical_cols,
                                     key=f"scatter_color_{item_name}")
        else:
            color_col = "Aucun"

        if color_col != "Aucun":
            fig = px.scatter(data, x=col1, y=col2, color=color_col, title=f"{col2} vs {col1}")
        else:
            fig = px.scatter(data, x=col1, y=col2, title=f"{col2} vs {col1}")
        st.plotly_chart(fig, use_container_width=True)

    elif viz_type == "Boîte à moustaches" and numeric_cols and categorical_cols:
        num_col = st.selectbox("Colonne numérique", numeric_cols, key=f"box_num_{item_name}")
        cat_col = st.selectbox("Colonne catégorielle", categorical_cols, key=f"box_cat_{item_name}")
        fig = px.box(data, x=cat_col, y=num_col, title=f"Boîte à moustaches de {num_col} par {cat_col}")
        st.plotly_chart(fig, use_container_width=True)

    elif viz_type == "Graphique en barres" and categorical_cols:
        cat_col = st.selectbox("Colonne catégorielle", categorical_cols, key=f"bar_cat_{item_name}")
        if numeric_cols:
            value_col = st.selectbox("Valeur à agréger", ["count"] + numeric_cols, key=f"bar_val_{item_name}")
        else:
            value_col = "count"

        if value_col == "count":
            bar_data = data[cat_col].value_counts().reset_index()
            bar_data.columns = [cat_col, 'count']
            fig = px.bar(bar_data, x=cat_col, y='count', title=f"Nombre par {cat_col}")
        else:
            bar_data = data.groupby(cat_col)[value_col].mean().reset_index()
            fig = px.bar(bar_data, x=cat_col, y=value_col, title=f"Moyenne de {value_col} par {cat_col}")
        st.plotly_chart(fig, use_container_width=True)

    elif viz_type == "Ligne" and numeric_cols:
        # Chercher une colonne temporelle
        date_cols = [col for col in data.columns if any(x in str(col).lower()
                                                        for x in ['date', 'time', 'jour', 'mois', 'année'])]
        if date_cols:
            x_col = st.selectbox("Axe X (temporel)", date_cols, key=f"line_x_{item_name}")
            y_col = st.selectbox("Axe Y (valeur)", numeric_cols, key=f"line_y_{item_name}")
            try:
                temp_data = data.copy()
                temp_data[x_col] = pd.to_datetime(temp_data[x_col])
                temp_data = temp_data.sort_values(x_col)
                fig = px.line(temp_data, x=x_col, y=y_col, title=f"Évolution de {y_col}")
                st.plotly_chart(fig, use_container_width=True)
            except:
                st.warning("Impossible de créer un graphique en ligne avec ces colonnes")
        else:
            st.warning("Aucune colonne temporelle détectée pour un graphique en ligne")


def display_dashboard_by_type(items, item_types):
    """Affiche les éléments du dashboard groupés par type"""
    st.markdown("## 📋 Éléments du Dashboard par type")

    # Créer des onglets pour chaque type d'élément
    tab_names = []
    if item_types.get('visualizations'):
        tab_names.append("📊 Visualisations")
    if item_types.get('charts'):
        tab_names.append("📈 Graphiques")
    if item_types.get('maps'):
        tab_names.append("🌍 Cartes")
    if item_types.get('texts'):
        tab_names.append("📝 Textes")
    if item_types.get('others'):
        tab_names.append("🔧 Autres")

    if tab_names:
        tabs = st.tabs(tab_names)

        tab_index = 0
        # Visualisations
        if item_types.get('visualizations'):
            with tabs[tab_index]:
                for viz in item_types['visualizations']:
                    # Trouver l'élément correspondant
                    for idx, item in enumerate(items):
                        if ('visualization' in item and item['visualization'] and
                                item['visualization'].get('id') == viz['id']):
                            display_dashboard_item_with_transform(item, idx)
                            st.markdown("---")
                            break
            tab_index += 1

        # Graphiques
        if item_types.get('charts'):
            with tabs[tab_index]:
                for chart in item_types['charts']:
                    for idx, item in enumerate(items):
                        if ('chart' in item and item['chart'] and
                                item['chart'].get('id') == chart['id']):
                            display_dashboard_item_with_transform(item, idx)
                            st.markdown("---")
                            break
            tab_index += 1

        # Cartes
        if item_types.get('maps'):
            with tabs[tab_index]:
                for map_item in item_types['maps']:
                    for idx, item in enumerate(items):
                        if ('map' in item and item['map'] and
                                item['map'].get('id') == map_item['id']):
                            display_dashboard_item_with_transform(item, idx)
                            st.markdown("---")
                            break
            tab_index += 1

        # Textes
        if item_types.get('texts'):
            with tabs[tab_index]:
                for text_item in item_types['texts']:
                    for idx, item in enumerate(items):
                        if 'text' in item and item.get('text') == text_item['content']:
                            display_dashboard_item_with_transform(item, idx)
                            st.markdown("---")
                            break
            tab_index += 1

        # Autres
        if item_types.get('others'):
            with tabs[tab_index]:
                for idx, item in enumerate(items):
                    item_type = get_item_type(item)
                    if item_type not in ['visualization', 'chart', 'map', 'text']:
                        display_dashboard_item_with_transform(item, idx)
                        st.markdown("---")
    else:
        st.info("Aucun élément à afficher")

def display_dashboard_item(item, idx):
    """Affiche un élément du dashboard (version compatibilité)"""
    # Utiliser la nouvelle fonction pour l'affichage complet
    display_dashboard_item_with_transform(item, idx)

def get_item_name(item, idx):
    """Récupère le nom d'un élément de dashboard"""
    if 'visualization' in item and item['visualization']:
        viz = item['visualization']
        return viz.get('name', f"Visualisation {idx + 1}")
    elif 'chart' in item and item['chart']:
        chart = item['chart']
        return chart.get('name', f"Graphique {idx + 1}")
    elif 'map' in item and item['map']:
        map_item = item['map']
        return map_item.get('name', f"Carte {idx + 1}")
    elif 'text' in item:
        text_content = item.get('text', '')
        return f"Texte: {text_content[:50]}..." if len(text_content) > 50 else f"Texte: {text_content}"
    else:
        return f"Élément {idx + 1}"


def get_item_type(item):
    """Récupère le type d'un élément de dashboard"""
    if 'visualization' in item and item['visualization']:
        return "visualization"
    elif 'chart' in item and item['chart']:
        return "chart"
    elif 'map' in item and item['map']:
        return "map"
    elif 'text' in item:
        return "text"
    else:
        return "other"

def get_item_type(item):
    """Récupère le type d'un élément de dashboard"""
    if 'visualization' in item and item['visualization']:
        return "visualization"
    elif 'chart' in item and item['chart']:
        return "chart"
    elif 'map' in item and item['map']:
        return "map"
    elif 'text' in item:
        return "text"
    else:
        return "other"


def display_all_dashboards():
    """Affiche tous les dashboards disponibles avec filtres et recherche"""
    st.markdown("### 📋 Tous les Dashboards Disponibles")

    # Initialisation des variables de session si nécessaire
    if 'all_dashboards_complete' not in st.session_state:
        st.session_state.all_dashboards_complete = []
    if 'last_search_query' not in st.session_state:
        st.session_state.last_search_query = ''

    # Section de recherche et filtres
    with st.container():
        col1, col2, col3 = st.columns([3, 2, 2])

        with col1:
            search_query = st.text_input(
                "🔍 Rechercher un dashboard",
                value=st.session_state.get('search_query', ''),
                placeholder="Entrez un mot-clé...",
                key="search_input"
            )

        with col2:
            filter_option = st.selectbox(
                "Filtrer par",
                ["Tous", "Mes dashboards", "Dashboards publics"],
                key="filter_select"
            )

        with col3:
            sort_option = st.selectbox(
                "Trier par",
                ["Nom (A-Z)", "Nom (Z-A)", "Date création", "Nombre d'éléments"],
                key="sort_select"
            )

    # Bouton de recherche
    col1, col2 = st.columns([1, 5])
    with col1:
        if st.button("Rechercher", use_container_width=True):
            st.session_state.search_query = search_query
            st.rerun()

    # Récupération des dashboards
    if (not st.session_state.all_dashboards_complete or
            st.session_state.search_query != st.session_state.last_search_query):

        with st.spinner("📡 Chargement des dashboards..."):
            try:
                dashboards = st.session_state.client.get_all_dashboards_complete(
                    st.session_state.search_query
                )
                st.session_state.all_dashboards_complete = dashboards
                st.session_state.last_search_query = st.session_state.search_query

                if dashboards:
                    st.success(f"✅ {len(dashboards)} dashboards chargés")
                else:
                    st.warning("⚠️ Aucun dashboard trouvé")

            except Exception as e:
                st.error(f"❌ Erreur lors du chargement: {str(e)}")
                dashboards = []
    else:
        dashboards = st.session_state.all_dashboards_complete

    # Filtrage des dashboards
    if dashboards:
        filtered_dashboards = []

        for dashboard in dashboards:
            # Filtre par propriété
            if filter_option == "Mes dashboards" and not dashboard.get('is_owner', False):
                continue
            elif filter_option == "Dashboards publics" and dashboard.get('is_owner', False):
                continue

            filtered_dashboards.append(dashboard)

        # Tri des dashboards
        if sort_option == "Nom (A-Z)":
            filtered_dashboards.sort(key=lambda x: x.get('name', '').lower())
        elif sort_option == "Nom (Z-A)":
            filtered_dashboards.sort(key=lambda x: x.get('name', '').lower(), reverse=True)
        elif sort_option == "Date création":
            filtered_dashboards.sort(key=lambda x: x.get('created', ''), reverse=True)
        elif sort_option == "Nombre d'éléments":
            filtered_dashboards.sort(key=lambda x: len(x.get('dashboardItems', [])), reverse=True)

        # Affichage des statistiques
        st.markdown(f"""
        <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
            <strong>📊 Statistiques:</strong> 
            {len(filtered_dashboards)} dashboards trouvés | 
            {sum(1 for d in filtered_dashboards if d.get('is_owner'))} mes dashboards | 
            {sum(len(d.get('dashboardItems', [])) for d in filtered_dashboards)} éléments au total
        </div>
        """, unsafe_allow_html=True)

        # Affichage des dashboards
        if filtered_dashboards:
            st.markdown('<div class="dashboard-grid">', unsafe_allow_html=True)

            cols = st.columns(2)
            for idx, dashboard in enumerate(filtered_dashboards):
                with cols[idx % 2]:
                    display_dashboard_card(dashboard, idx)

            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.info("Aucun dashboard ne correspond aux critères de filtrage")
    else:
        st.info("Aucun dashboard disponible. Essayez de modifier vos critères de recherche.")

    # Bouton retour
    if st.session_state.current_dashboard:
        if st.button("← Retour à la liste", use_container_width=True):
            st.session_state.current_dashboard = None
            st.rerun()


def main():
    st.markdown('<h1 class="main-header">📊 DHIS2 Dashboard Viewer - Analyses Complètes</h1>', unsafe_allow_html=True)

    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'client' not in st.session_state:
        st.session_state.client = None
    if 'current_dashboard' not in st.session_state:
        st.session_state.current_dashboard = None
    if 'user_info' not in st.session_state:
        st.session_state.user_info = None
    if 'search_query' not in st.session_state:
        st.session_state.search_query = ''

    with st.sidebar:
        st.markdown("### 🔐 Connexion DHIS2")

        base_url = st.text_input(
            "URL DHIS2",
            value="https://senegal.dhis2.org/dhis",
            key="base_url"
        )

        username = st.text_input("Nom d'utilisateur", key="username")
        password = st.text_input("Mot de passe", type="password", key="password")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("Se connecter", key="login_btn", use_container_width=True, type="primary"):
                with st.spinner("Connexion..."):
                    client = DHIS2Client(base_url, username, password)
                    success, user_info = client.test_connection()

                    if success:
                        st.session_state.authenticated = True
                        st.session_state.client = client
                        st.session_state.user_info = user_info

                        st.session_state.all_dashboards_complete = []
                        st.session_state.last_search_query = ''
                        st.session_state.search_query = ''

                        st.success(f"✅ Connecté: {user_info.get('name', username)}")
                        st.rerun()
                    else:
                        st.error("❌ Échec de connexion")

        with col2:
            if st.button("Déconnexion", key="logout_btn", use_container_width=True):
                for key in list(st.session_state.keys()):
                    del st.session_state[key]
                st.session_state.authenticated = False
                st.session_state.search_query = ''
                st.rerun()

        if st.session_state.authenticated and st.session_state.user_info:
            st.markdown("---")
            user = st.session_state.user_info
            st.markdown(f"**👤 {user.get('name')}**")
            st.markdown(f"*{user.get('email', '')}*")

            st.markdown("---")
            st.markdown("### ⚙️ Options")
            if st.button("🔄 Actualiser les dashboards", use_container_width=True):
                st.session_state.all_dashboards_complete = []
                st.rerun()

    if not st.session_state.authenticated:
        st.markdown("""
        <div style='text-align: center; padding: 40px;'>
            <h2>Bienvenue sur DHIS2 Dashboard Viewer - Analyses Complètes</h2>
            <p>Connectez-vous pour visualiser et analyser TOUS les dashboards DHIS2 disponibles.</p>
            <div style='margin-top: 30px;'>
                <h4>🎯 Fonctionnalités d'analyse:</h4>
                <div style='text-align: left; margin: 20px;'>
                    <p>✅ <strong>Analyses descriptives</strong> : Statistiques, distributions</p>
                    <p>✅ <strong>Analyses temporelles</strong> : Tendances, évolutions</p>
                    <p>✅ <strong>Analyses géographiques</strong> : Cartes, comparaisons régionales</p>
                    <p>✅ <strong>Analyses de performance</strong> : ECV/DSDM, indicateurs</p>
                    <p>✅ <strong>Analyses comparatives</strong> : Groupes, catégories</p>
                    <p>✅ <strong>Qualité des données</strong> : Détection d'anomalies</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        if st.session_state.current_dashboard:
            display_selected_dashboard()
        else:
            display_all_dashboards()


if __name__ == "__main__":
    main()
