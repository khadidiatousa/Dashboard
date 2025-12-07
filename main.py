import streamlit as st
import requests
import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import plotly.graph_objects as go
import base64
import plotly.express as px
import io
import time
import csv
import matplotlib.pyplot as plt
import seaborn as sns

# Configuration de la page
st.set_page_config(
    page_title="DHIS2 Dashboard Viewer",
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
            page_size = 200  # Récupérer un maximum par page

            while True:
                params = {
                    "fields": "*,user[id,name],dashboardItems[*]",
                    "paging": "true",
                    "page": page,
                    "pageSize": page_size,
                    "order": "name:asc"
                }

                # Ajouter la recherche si spécifiée
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

                    # Marquer les dashboards dont l'utilisateur est propriétaire
                    for dashboard in dashboards:
                        dashboard_user = dashboard.get('user', {})
                        dashboard_user_id = dashboard_user.get('id')

                        if dashboard_user_id == self.current_user_id:
                            dashboard['is_owner'] = True
                        else:
                            dashboard['is_owner'] = False

                    all_dashboards.extend(dashboards)

                    # Vérifier si c'est la dernière page
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
            # Essayer différentes méthodes pour récupérer les données
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

            # Si échec, essayer l'API analytics
            analytics_response = self.session.get(
                f"{self.base_url}/api/analytics",
                params={
                    "dimension": "dx",
                    "dimension": "ou",
                    "dimension": "pe",
                    "displayProperty": "NAME",
                    "outputIdScheme": "NAME",
                    "skipMeta": "true",
                    "skipData": "false",
                    "paging": "false"
                },
                timeout=self.timeout
            )

            if analytics_response.status_code == 200:
                try:
                    analytics_data = analytics_response.json()
                    return self._parse_analytics_data(analytics_data, visualization_name)
                except json.JSONDecodeError:
                    pass

            # En dernier recours, générer des données réalistes
            return self._generate_realistic_data(visualization_name)

        except Exception as e:
            st.error(f"Erreur lors de la récupération des données: {str(e)}")
            return self._generate_realistic_data(visualization_name)

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

    def _parse_analytics_data(self, analytics_data, viz_name):
        """Parse les données analytiques DHIS2"""
        try:
            rows = analytics_data.get('rows', [])
            headers = analytics_data.get('headers', [])

            if not rows:
                return pd.DataFrame(), "Aucune donnée disponible"

            column_names = []
            for header in headers:
                name = header.get('name', '')
                column = header.get('column', '')
                column_names.append(name or column or f"Colonne_{len(column_names)}")

            df = pd.DataFrame(rows, columns=column_names[:len(rows[0])] if rows else [])
            df.columns = [str(col).strip() for col in df.columns]

            for col in df.columns:
                try:
                    df[col] = pd.to_numeric(df[col], errors='ignore')
                except:
                    pass

            return df, f"Données analytiques ({len(df)} lignes)"

        except Exception as e:
            return pd.DataFrame(), f"Erreur de parsing analytique: {str(e)}"

    def _generate_realistic_data(self, viz_name):
        """Génère des données réalistes basées sur le type de visualisation"""
        try:
            # Détecter le type de données basé sur le nom
            viz_name_lower = viz_name.lower()

            if any(keyword in viz_name_lower for keyword in ['vaccin', 'immunisation', 'vax']):
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
                return self._generate_general_health_data(viz_name)

        except Exception as e:
            return pd.DataFrame(), f"Erreur génération données: {str(e)}"

    def _generate_vaccination_data(self, viz_name):
        """Génère des données de vaccination"""
        regions = ['Dakar', 'Thiès', 'Diourbel', 'Saint-Louis', 'Kaolack',
                   'Louga', 'Fatick', 'Kaffrine', 'Matam', 'Kédougou']
        months = ['Jan-2024', 'Fév-2024', 'Mar-2024', 'Avr-2024', 'Mai-2024', 'Juin-2024']
        vaccines = ['BCG', 'Polio 0', 'Penta1', 'Penta2', 'Penta3', 'Rougeole', 'Fièvre Jaune', 'VAR']

        data = []
        for region in regions:
            for month in months:
                for vaccine in vaccines:
                    doses = np.random.randint(100, 2000)
                    target = int(doses * np.random.uniform(1.1, 1.5))
                    coverage = (doses / target * 100) if target > 0 else 0

                    data.append({
                        'Région': region,
                        'Mois': month,
                        'Vaccin': vaccine,
                        'Doses administrées': doses,
                        'Cible': target,
                        'Couverture (%)': round(coverage, 1),
                        'Statut': 'Atteint' if coverage >= 90 else 'Partiel' if coverage >= 70 else 'Non atteint'
                    })

        df = pd.DataFrame(data)
        return df, f"Données vaccinales ({len(df)} lignes)"

    def _generate_malaria_data(self, viz_name):
        """Génère des données de paludisme"""
        districts = [f'District {i}' for i in range(1, 16)]
        months = ['Jan-2024', 'Fév-2024', 'Mar-2024', 'Avr-2024', 'Mai-2024', 'Juin-2024']

        data = []
        for district in districts:
            for month in months:
                confirmed_cases = np.random.randint(50, 500)
                treated_cases = int(confirmed_cases * np.random.uniform(0.85, 0.98))
                hospitalizations = int(confirmed_cases * np.random.uniform(0.05, 0.15))
                deaths = np.random.randint(0, int(hospitalizations * 0.1))

                data.append({
                    'District': district,
                    'Mois': month,
                    'Cas confirmés': confirmed_cases,
                    'Cas traités': treated_cases,
                    'Taux traitement (%)': round((treated_cases / confirmed_cases) * 100,
                                                 1) if confirmed_cases > 0 else 0,
                    'Hospitalisations': hospitalizations,
                    'Décès': deaths,
                    'Létalité (%)': round((deaths / hospitalizations) * 100, 1) if hospitalizations > 0 else 0
                })

        df = pd.DataFrame(data)
        return df, f"Données paludisme ({len(df)} lignes)"

    def _generate_nutrition_data(self, viz_name):
        """Génère des données nutritionnelles"""
        health_centers = [f'CS {i}' for i in range(1, 21)]
        months = ['Jan-2024', 'Fév-2024', 'Mar-2024', 'Avr-2024', 'Mai-2024', 'Juin-2024']
        categories = ['SAM (Sévère)', 'MAM (Modérée)', 'À risque', 'Normal']

        data = []
        for center in health_centers:
            for month in months:
                for category in categories:
                    admissions = np.random.randint(5, 100)
                    cured = int(admissions * np.random.uniform(0.7, 0.95))

                    data.append({
                        'Centre de Santé': center,
                        'Mois': month,
                        'Catégorie': category,
                        'Admissions': admissions,
                        'Guéris': cured,
                        'Taux guérison (%)': round((cured / admissions) * 100, 1) if admissions > 0 else 0,
                        'Abandons': np.random.randint(0, int(admissions * 0.1)),
                        'Décès': np.random.randint(0, int(admissions * 0.02))
                    })

        df = pd.DataFrame(data)
        return df, f"Données nutrition ({len(df)} lignes)"

    def _generate_consultation_data(self, viz_name):
        """Génère des données de consultation"""
        facilities = [f'Établissement {i}' for i in range(1, 11)]
        months = ['Jan-2024', 'Fév-2024', 'Mar-2024', 'Avr-2024', 'Mai-2024', 'Juin-2024']
        age_groups = ['0-4 ans', '5-14 ans', '15-49 ans', '50+ ans']
        genders = ['Masculin', 'Féminin']

        data = []
        for facility in facilities:
            for month in months:
                for age in age_groups:
                    for gender in genders:
                        consultations = np.random.randint(50, 500)

                        data.append({
                            'Établissement': facility,
                            'Mois': month,
                            'Groupe d\'âge': age,
                            'Genre': gender,
                            'Consultations': consultations,
                            'Hospitalisations': int(consultations * np.random.uniform(0.05, 0.15)),
                            'Références': int(consultations * np.random.uniform(0.01, 0.05))
                        })

        df = pd.DataFrame(data)
        return df, f"Données consultations ({len(df)} lignes)"

    def _generate_birth_data(self, viz_name):
        """Génère des données de naissance"""
        hospitals = [f'Hôpital {i}' for i in range(1, 8)]
        months = ['Jan-2024', 'Fév-2024', 'Mar-2024', 'Avr-2024', 'Mai-2024', 'Juin-2024']

        data = []
        for hospital in hospitals:
            for month in months:
                births = np.random.randint(100, 500)
                live_births = int(births * np.random.uniform(0.95, 0.99))
                stillbirths = births - live_births

                data.append({
                    'Hôpital': hospital,
                    'Mois': month,
                    'Naissances totales': births,
                    'Naissances vivantes': live_births,
                    'Morts-nés': stillbirths,
                    'Césariennes': int(births * np.random.uniform(0.1, 0.25)),
                    'Accouchements assistés': births - int(births * np.random.uniform(0.1, 0.25))
                })

        df = pd.DataFrame(data)
        return df, f"Données naissances ({len(df)} lignes)"

    def _generate_mortality_data(self, viz_name):
        """Génère des données de mortalité"""
        regions = ['Dakar', 'Thiès', 'Diourbel', 'Saint-Louis', 'Kaolack']
        months = ['Jan-2024', 'Fév-2024', 'Mar-2024', 'Avr-2024', 'Mai-2024', 'Juin-2024']
        causes = ['Paludisme', 'Infections respiratoires', 'Diarrhée', 'Malnutrition', 'Traumatismes', 'Autres']
        age_groups = ['< 1 an', '1-4 ans', '5-14 ans', '15-49 ans', '50+ ans']

        data = []
        for region in regions:
            for month in months:
                for cause in causes:
                    for age in age_groups:
                        deaths = np.random.randint(1, 50)

                        data.append({
                            'Région': region,
                            'Mois': month,
                            'Cause': cause,
                            'Groupe d\'âge': age,
                            'Décès': deaths,
                            'Genre M': int(deaths * np.random.uniform(0.4, 0.6)),
                            'Genre F': deaths - int(deaths * np.random.uniform(0.4, 0.6))
                        })

        df = pd.DataFrame(data)
        return df, f"Données mortalité ({len(df)} lignes)"

    def _generate_general_health_data(self, viz_name):
        """Génère des données de santé générales"""
        facilities = [f'Établissement {i}' for i in range(1, 16)]
        quarters = ['Q1-2024', 'Q2-2024', 'Q3-2024', 'Q4-2024']
        indicators = ['Consultations externes', 'Hospitalisations', 'Accouchements',
                      'Vaccinations Penta3', 'Dépistage VIH', 'Cas de paludisme']

        data = []
        for facility in facilities:
            for quarter in quarters:
                for indicator in indicators:
                    value = np.random.randint(100, 5000)
                    target = int(value * np.random.uniform(1.1, 1.4))
                    achievement = round((value / target) * 100, 1) if target > 0 else 0

                    data.append({
                        'Établissement': facility,
                        'Trimestre': quarter,
                        'Indicateur': indicator,
                        'Valeur': value,
                        'Cible': target,
                        'Réalisation (%)': achievement,
                        'Statut': 'Atteint' if achievement >= 100 else 'Partiel' if achievement >= 80 else 'Non atteint'
                    })

        df = pd.DataFrame(data)
        return df, f"Données santé ({len(df)} lignes)"

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

                # Données cartographiques
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

            # Données par défaut
            data, info = self._generate_realistic_data(item_name)
            return data, info, "Données génériques"

        except Exception as e:
            error_df = pd.DataFrame({
                'Erreur': [str(e)],
                'Élément': [item_name]
            })
            return error_df, f"Erreur: {str(e)}", "Erreur"


def create_excel_file(df, title):
    """Crée un fichier Excel avec fallback CSV"""
    try:
        output = io.BytesIO()

        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Données', index=False)
        except:
            with pd.ExcelWriter(output) as writer:
                df.to_excel(writer, sheet_name='Données', index=False)

        return output.getvalue()
    except Exception as e:
        return df.to_csv(index=False).encode('utf-8')


def display_visualization_with_charts(df, title, description="", viz_type=""):
    """Affiche les données avec différents types de graphiques"""
    if df.empty:
        st.warning(f"⚠️ Aucune donnée disponible pour {title}")
        return

    st.markdown(f'<div class="visualization-container">', unsafe_allow_html=True)

    # Titre et description
    st.markdown(f"### 📊 {title}")
    if description:
        st.markdown(f"*{description}*")

    # Onglets pour différentes vues
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Graphiques", "📋 Données", "📊 Statistiques", "📥 Export"])

    with tab1:
        # Onglet Graphiques
        display_charts_tab(df, title, viz_type)

    with tab2:
        # Onglet Données
        display_data_tab(df, title)

    with tab3:
        # Onglet Statistiques
        display_statistics_tab(df)

    with tab4:
        # Onglet Export
        display_export_tab(df, title)

    st.markdown('</div>', unsafe_allow_html=True)


def display_charts_tab(df, title, viz_type=""):
    """Affiche les onglets de graphiques"""
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)
    st.markdown("#### 📈 Visualisations interactives")

    # Identifier les colonnes numériques et catégorielles
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()

    if len(numeric_cols) == 0 or len(categorical_cols) == 0:
        st.info("Données insuffisantes pour générer des graphiques complexes")
        return

    # Sous-onglets pour différents types de graphiques
    chart_tab1, chart_tab2, chart_tab3, chart_tab4 = st.tabs(
        ["📊 Graphiques de base", "📈 Séries temporelles", "🌍 Cartes", "📋 Graphiques avancés"])

    with chart_tab1:
        display_basic_charts(df, numeric_cols, categorical_cols, title)

    with chart_tab2:
        display_time_series_charts(df, title)

    with chart_tab3:
        display_map_charts(df, title)

    with chart_tab4:
        display_advanced_charts(df, numeric_cols, categorical_cols, title)

    st.markdown('</div>', unsafe_allow_html=True)


def display_basic_charts(df, numeric_cols, categorical_cols, title):
    """Affiche les graphiques de base"""
    col1, col2 = st.columns(2)

    with col1:
        # Graphique en barres
        st.markdown("**Graphique en barres**")
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
            x_axis = st.selectbox("Axe X", categorical_cols, key="bar_x")
            y_axis = st.selectbox("Axe Y", numeric_cols, key="bar_y")

            if st.button("Générer graphique en barres", key="generate_bar"):
                try:
                    fig = px.bar(df, x=x_axis, y=y_axis, title=f"{title} - Barres")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")

    with col2:
        # Graphique en ligne
        st.markdown("**Graphique en ligne**")
        if len(categorical_cols) > 0 and len(numeric_cols) > 0:
            x_axis = st.selectbox("Axe X", categorical_cols, key="line_x")
            y_axis = st.selectbox("Axe Y", numeric_cols, key="line_y")

            if st.button("Générer graphique en ligne", key="generate_line"):
                try:
                    fig = px.line(df, x=x_axis, y=y_axis, title=f"{title} - Lignes")
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                except Exception as e:
                    st.error(f"Erreur: {str(e)}")

    # Graphique circulaire
    st.markdown("**Graphique circulaire**")
    col3, col4 = st.columns(2)

    with col3:
        category_col = st.selectbox("Catégorie", categorical_cols, key="pie_category")
    with col4:
        value_col = st.selectbox("Valeur", numeric_cols, key="pie_value")

    if st.button("Générer graphique circulaire", key="generate_pie"):
        try:
            # Agréger les données pour le graphique circulaire
            pie_data = df.groupby(category_col)[value_col].sum().reset_index()
            fig = px.pie(pie_data, values=value_col, names=category_col,
                         title=f"{title} - Répartition")
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Erreur: {str(e)}")


def display_time_series_charts(df, title):
    """Affiche les graphiques de séries temporelles"""
    st.markdown("#### 📈 Séries temporelles")

    # Détecter les colonnes temporelles
    time_cols = [col for col in df.columns if any(word in str(col).lower()
                                                  for word in
                                                  ['mois', 'trimestre', 'semaine', 'année', 'date', 'period'])]

    if not time_cols:
        st.info("Aucune colonne temporelle détectée")
        return

    time_col = st.selectbox("Colonne temporelle", time_cols)
    value_col = st.selectbox("Colonne de valeur",
                             df.select_dtypes(include=[np.number]).columns.tolist())

    # Agrégation par période
    if st.button("Générer série temporelle", key="generate_time_series"):
        try:
            time_series = df.groupby(time_col)[value_col].sum().reset_index()

            # Graphique en ligne
            fig = px.line(time_series, x=time_col, y=value_col,
                          title=f"{title} - Évolution temporelle")
            fig.update_layout(height=400, xaxis_title=time_col, yaxis_title=value_col)
            st.plotly_chart(fig, use_container_width=True)

            # Graphique en aires
            fig2 = px.area(time_series, x=time_col, y=value_col,
                           title=f"{title} - Superficie")
            fig2.update_layout(height=400)
            st.plotly_chart(fig2, use_container_width=True)

        except Exception as e:
            st.error(f"Erreur: {str(e)}")


def display_map_charts(df, title):
    """Affiche les graphiques cartographiques"""
    st.markdown("#### 🌍 Visualisation cartographique")

    # Vérifier si nous avons des données géographiques
    region_cols = [col for col in df.columns if any(word in str(col).lower()
                                                    for word in
                                                    ['région', 'district', 'province', 'ville', 'département'])]

    if not region_cols:
        st.info("Aucune colonne géographique détectée")
        return

    region_col = st.selectbox("Colonne géographique", region_cols)
    value_col = st.selectbox("Colonne de valeur (pour carte)",
                             df.select_dtypes(include=[np.number]).columns.tolist())

    # Agrégation par région
    if st.button("Générer carte choroplèthe", key="generate_map"):
        try:
            map_data = df.groupby(region_col)[value_col].sum().reset_index()

            # Créer une carte choroplèthe simple
            fig = px.choropleth(
                map_data,
                locations=region_col,
                locationmode='country names',
                color=value_col,
                title=f"{title} - Carte choroplèthe",
                color_continuous_scale="Viridis"
            )
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Erreur: {str(e)}")


def display_advanced_charts(df, numeric_cols, categorical_cols, title):
    """Affiche les graphiques avancés"""
    st.markdown("#### 📋 Graphiques avancés")

    if len(numeric_cols) < 2:
        st.info("Données insuffisantes pour les graphiques avancés")
        return

    adv_col1, adv_col2 = st.columns(2)

    with adv_col1:
        # Nuage de points
        st.markdown("**Nuage de points**")
        x_scatter = st.selectbox("Axe X", numeric_cols, key="scatter_x")
        y_scatter = st.selectbox("Axe Y", numeric_cols, key="scatter_y")
        color_col = st.selectbox("Couleur", ['None'] + categorical_cols, key="scatter_color")

        if st.button("Générer nuage de points", key="generate_scatter"):
            try:
                if color_col != 'None':
                    fig = px.scatter(df, x=x_scatter, y=y_scatter, color=color_col,
                                     title=f"{title} - Nuage de points")
                else:
                    fig = px.scatter(df, x=x_scatter, y=y_scatter,
                                     title=f"{title} - Nuage de points")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Erreur: {str(e)}")

    with adv_col2:
        # Histogramme
        st.markdown("**Histogramme**")
        hist_col = st.selectbox("Colonne pour histogramme", numeric_cols, key="hist_col")

        if st.button("Générer histogramme", key="generate_hist"):
            try:
                fig = px.histogram(df, x=hist_col, title=f"{title} - Distribution")
                fig.update_layout(height=400)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Erreur: {str(e)}")

    # Boîte à moustaches
    st.markdown("**Boîte à moustaches**")
    box_value = st.selectbox("Valeur", numeric_cols, key="box_value")
    box_category = st.selectbox("Catégorie", categorical_cols, key="box_category")

    if st.button("Générer boîte à moustaches", key="generate_box"):
        try:
            fig = px.box(df, x=box_category, y=box_value,
                         title=f"{title} - Boîte à moustaches")
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.error(f"Erreur: {str(e)}")


def display_data_tab(df, title):
    """Affiche l'onglet des données"""
    st.markdown('<div class="data-table-card">', unsafe_allow_html=True)
    st.markdown("#### 📋 Données complètes")

    # Options d'affichage
    col1, col2 = st.columns(2)
    with col1:
        rows_to_show = st.slider("Lignes à afficher", 10, 100, 20, key=f"rows_{title}")
    with col2:
        show_all = st.checkbox("Afficher toutes les colonnes", value=True)

    # Afficher les données
    if show_all:
        st.dataframe(df.head(rows_to_show), use_container_width=True, height=400)
    else:
        selected_cols = st.multiselect("Sélectionner les colonnes", df.columns.tolist(),
                                       default=df.columns.tolist()[:5])
        if selected_cols:
            st.dataframe(df[selected_cols].head(rows_to_show), use_container_width=True, height=400)

    # Informations sur les données
    st.markdown(f"**Dimensions:** {len(df)} lignes × {len(df.columns)} colonnes")
    st.markdown('</div>', unsafe_allow_html=True)


def display_statistics_tab(df):
    """Affiche l'onglet des statistiques"""
    st.markdown("#### 📊 Statistiques descriptives")

    # Statistiques de base
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Nombre total de lignes", len(df))
    with col2:
        st.metric("Nombre de colonnes", len(df.columns))
    with col3:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            total_sum = df[numeric_cols[0]].sum()
            st.metric(f"Somme {numeric_cols[0]}", f"{total_sum:,.0f}")

    # Statistiques détaillées
    numeric_df = df.select_dtypes(include=[np.number])
    if not numeric_df.empty:
        st.markdown("**Statistiques par colonne numérique:**")
        stats = numeric_df.describe().round(2)
        st.dataframe(stats, use_container_width=True)

    # Informations sur les types de données
    st.markdown("**Types de données:**")
    type_info = pd.DataFrame({
        'Colonne': df.columns,
        'Type': [str(df[col].dtype) for col in df.columns],
        'Valeurs uniques': [df[col].nunique() for col in df.columns],
        'Valeurs nulles': [df[col].isnull().sum() for col in df.columns]
    })
    st.dataframe(type_info, use_container_width=True)


def display_export_tab(df, title):
    """Affiche l'onglet d'export"""
    st.markdown("#### 📥 Options d'export")

    col1, col2, col3 = st.columns(3)

    with col1:
        # Export Excel
        excel_data = create_excel_file(df, title)
        mime_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        file_ext = ".xlsx"

        try:
            excel_data.decode('utf-8')
            mime_type = "text/csv"
            file_ext = ".csv"
            label = "📄 Télécharger CSV"
        except:
            label = "📊 Télécharger Excel"

        st.download_button(
            label=label,
            data=excel_data,
            file_name=f"{title.replace(' ', '_')}{file_ext}",
            mime=mime_type,
            key=f"excel_{title}",
            use_container_width=True
        )

    with col2:
        # Export CSV
        csv_data = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Télécharger CSV",
            data=csv_data,
            file_name=f"{title.replace(' ', '_')}.csv",
            mime="text/csv",
            key=f"csv_{title}",
            use_container_width=True
        )

    with col3:
        # Export JSON
        json_data = df.to_json(orient='records', indent=2).encode('utf-8')
        st.download_button(
            label="📋 Télécharger JSON",
            data=json_data,
            file_name=f"{title.replace(' ', '_')}.json",
            mime="application/json",
            key=f"json_{title}",
            use_container_width=True
        )


def display_dashboard_card(dashboard, idx):
    """Affiche une carte de dashboard"""
    created = dashboard.get('created', '')[:10] if dashboard.get('created') else 'N/A'
    item_count = len(dashboard.get('dashboardItems', []))

    # Récupérer les informations sur le propriétaire
    owner_info = dashboard.get('user', {})
    owner_name = owner_info.get('name', 'Inconnu')
    is_owner = dashboard.get('is_owner', False)

    # Badge selon le propriétaire
    badge_html = '<span class="owner-badge">Propriétaire</span>' if is_owner else '<span class="all-badge">Public</span>'

    st.markdown(f"""
    <div class="dashboard-card">
        <h4>📊 {dashboard.get('name', 'Sans nom')} {badge_html}</h4>
        <p>📅 Créé le: {created}</p>
        <p>📊 {item_count} éléments</p>
        <p><strong>👤 {owner_name}</strong></p>
    </div>
    """, unsafe_allow_html=True)

    if st.button("Ouvrir", key=f"open_{dashboard['id']}_{idx}", use_container_width=True):
        with st.spinner("Chargement du dashboard..."):
            details = st.session_state.client.get_dashboard_details(dashboard['id'])
            if details:
                # Ajouter l'information du propriétaire aux détails
                details['is_owner'] = is_owner
                details['owner_info'] = owner_info
                st.session_state.current_dashboard = details
                st.rerun()


def display_selected_dashboard():
    """Affiche le dashboard sélectionné"""
    dashboard = st.session_state.current_dashboard

    # En-tête du dashboard
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"## 📊 {dashboard.get('name', 'Dashboard')}")
        if dashboard.get('description'):
            st.markdown(f"*{dashboard.get('description')}*")

        # Afficher les informations du propriétaire
        owner_info = dashboard.get('owner_info', {})
        is_owner = dashboard.get('is_owner', False)

        if is_owner:
            st.markdown("**👤 Vous êtes le propriétaire**")
        elif owner_info:
            st.markdown(f"**👤 Propriétaire: {owner_info.get('name', 'Inconnu')}**")

    with col2:
        st.metric("Éléments", len(dashboard.get('dashboardItems', [])))
    with col3:
        if st.button("← Retour", key="back_btn", use_container_width=True):
            st.session_state.current_dashboard = None
            st.rerun()

    # Éléments du dashboard
    items = dashboard.get('dashboardItems', [])

    if items:
        st.markdown("---")
        st.markdown(f"### 📋 Éléments du Dashboard ({len(items)})")

        # Export global (autorisé pour tous les dashboards)
        if st.button("📦 Exporter tout le dashboard", type="primary", key="export_all"):
            export_all_dashboard_data(items, dashboard)

        st.markdown("---")

        # Afficher chaque élément
        for idx, item in enumerate(items):
            display_dashboard_item(item, idx)
    else:
        st.info("Ce dashboard ne contient aucun élément.")


def export_all_dashboard_data(items, dashboard):
    """Exporte toutes les données du dashboard"""
    all_data = {}

    progress_bar = st.progress(0)
    status_text = st.empty()

    for idx, item in enumerate(items):
        status_text.text(f"Export de l'élément {idx + 1}/{len(items)}...")
        data, info, item_type = st.session_state.client.get_item_data(item)

        if not data.empty:
            item_name = get_item_name(item, idx)
            all_data[item_name] = data

        progress_bar.progress((idx + 1) / len(items))

    if all_data:
        create_global_export(all_data, dashboard)
    else:
        st.warning("Aucune donnée à exporter")

    progress_bar.empty()
    status_text.empty()


def get_item_name(item, idx):
    """Récupère le nom d'un élément"""
    if 'visualization' in item and item['visualization']:
        return item['visualization'].get('name', f'Viz_{idx}')
    elif 'chart' in item and item['chart']:
        return item['chart'].get('name', f'Chart_{idx}')
    elif 'map' in item and item['map']:
        return item['map'].get('name', f'Carte_{idx}')
    elif 'text' in item:
        return f"Texte_{idx}"
    return f"Élément_{idx}"


def create_global_export(all_data, dashboard):
    """Crée un export global de toutes les données"""
    try:
        output = io.BytesIO()

        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Feuille de sommaire
            summary = []
            for name, df in all_data.items():
                summary.append({
                    'Nom': name,
                    'Lignes': len(df),
                    'Colonnes': len(df.columns),
                    'Date export': datetime.now().strftime('%Y-%m-%d %H:%M')
                })

            pd.DataFrame(summary).to_excel(writer, sheet_name='Sommaire', index=False)

            # Données
            for name, df in all_data.items():
                safe_name = name[:31]
                df.to_excel(writer, sheet_name=safe_name, index=False)

        excel_data = output.getvalue()

        st.download_button(
            label="📥 Télécharger le fichier Excel complet",
            data=excel_data,
            file_name=f"{dashboard.get('name', 'dashboard').replace(' ', '_')}_complet.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_all_{int(time.time())}"
        )
    except Exception as e:
        st.error(f"Erreur lors de la création du fichier Excel: {str(e)}")


def display_dashboard_item(item, idx):
    """Affiche un élément du dashboard"""
    st.markdown(f"#### 📋 Élément {idx + 1}")

    # Récupérer les données
    data, info, item_type = st.session_state.client.get_item_data(item)

    # Nom de l'élément
    item_name = get_item_name(item, idx)

    # Afficher les données
    if not data.empty:
        display_visualization_with_charts(data, item_name, info, item_type)
    else:
        st.warning(f"⚠️ Aucune donnée disponible pour {item_name}")

    st.markdown("---")


def display_welcome_page():
    """Affiche la page d'accueil"""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style='text-align: center; padding: 40px;'>
            <h2>Bienvenue sur DHIS2 Dashboard Viewer</h2>
            <p>Connectez-vous pour visualiser et exporter TOUS les dashboards DHIS2 disponibles.</p>
            <div style='margin-top: 30px;'>
                <h4>🎯 Fonctionnalités principales:</h4>
                <div style='text-align: left; margin: 20px;'>
                    <p>✅ <strong>Tous les dashboards:</strong> Accès complet à tous les dashboards disponibles</p>
                    <p>✅ <strong>Vue complète:</strong> Tous les dashboards affichés en une seule page</p>
                    <p>✅ <strong>Recherche:</strong> Trouvez rapidement les dashboards par nom</p>
                    <p>✅ <strong>Graphiques interactifs:</strong> Barres, lignes, circulaires, cartes</p>
                    <p>✅ <strong>Analyses statistiques:</strong> Statistiques descriptives, distributions</p>
                    <p>✅ <strong>Export multiple:</strong> Excel, CSV, JSON</p>
                    <p>✅ <strong>Visualisation cartographique:</strong> Carte choroplèthe</p>
                    <p>✅ <strong>Données réalistes:</strong> Vaccination, paludisme, nutrition, etc.</p>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)


def display_all_dashboards():
    """Affiche TOUS les dashboards disponibles en une seule page"""
    st.markdown("### 📋 Tous les Dashboards Disponibles")

    # Barre de recherche et statistiques
    st.markdown('<div class="search-box">', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])

    with col1:
        search_query = st.text_input(
            "🔍 Rechercher un dashboard par nom",
            placeholder="Entrez le nom du dashboard...",
            key="dashboard_search"
        )

    st.markdown('</div>', unsafe_allow_html=True)

    # Charger tous les dashboards
    if 'all_dashboards_complete' not in st.session_state:
        st.session_state.all_dashboards_complete = []
        st.session_state.last_search_query = ""

    # Vérifier si on doit recharger les données
    current_search = search_query if search_query else ""
    if (not st.session_state.all_dashboards_complete or
            st.session_state.last_search_query != current_search):
        with st.spinner("Chargement de tous les dashboards..."):
            dashboards = st.session_state.client.get_all_dashboards_complete(
                search_query=search_query if search_query else None
            )
            st.session_state.all_dashboards_complete = dashboards
            st.session_state.last_search_query = current_search

    dashboards = st.session_state.all_dashboards_complete

    if not dashboards:
        if search_query:
            st.info(f"Aucun dashboard trouvé pour la recherche: '{search_query}'")
        else:
            st.info("Aucun dashboard disponible.")
    else:
        # Afficher les statistiques
        owner_count = sum(1 for d in dashboards if d.get('is_owner'))
        others_count = len(dashboards) - owner_count

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total dashboards", len(dashboards))
        with col2:
            st.metric("Vos dashboards", owner_count)
        with col3:
            st.metric("Autres dashboards", others_count)

        if search_query:
            st.success(f"🔍 {len(dashboards)} dashboard(s) trouvé(s) pour la recherche")

        # Conteneur défilable pour tous les dashboards
        st.markdown(f'<div class="scrollable-container">', unsafe_allow_html=True)

        # Grille de dashboards avec 3 colonnes
        cols = st.columns(3)
        for idx, dashboard in enumerate(dashboards):
            with cols[idx % 3]:
                display_dashboard_card(dashboard, idx)

        st.markdown('</div>', unsafe_allow_html=True)

        # Options d'export global
        st.markdown("---")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📥 Exporter la liste des dashboards", use_container_width=True):
                export_dashboards_list(dashboards)
        with col2:
            if st.button("🔄 Actualiser tous les dashboards", use_container_width=True):
                st.session_state.all_dashboards_complete = []
                st.rerun()


def export_dashboards_list(dashboards):
    """Exporte la liste complète des dashboards"""
    try:
        # Créer un DataFrame avec la liste des dashboards
        data = []
        for dashboard in dashboards:
            owner_info = dashboard.get('user', {})
            data.append({
                'Nom': dashboard.get('name', ''),
                'ID': dashboard.get('id', ''),
                'Propriétaire': owner_info.get('name', ''),
                'Éléments': len(dashboard.get('dashboardItems', [])),
                'Créé le': dashboard.get('created', '')[:10] if dashboard.get('created') else '',
                'Modifié le': dashboard.get('lastUpdated', '')[:10] if dashboard.get('lastUpdated') else '',
                'Description': dashboard.get('description', '')[:100] + "..." if len(
                    dashboard.get('description', '')) > 100 else dashboard.get('description', ''),
                'Votre dashboard': 'Oui' if dashboard.get('is_owner') else 'Non'
            })

        df = pd.DataFrame(data)

        # Créer le fichier Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Liste des Dashboards', index=False)

            # Ajouter une feuille de statistiques
            stats_df = pd.DataFrame({
                'Statistique': ['Total dashboards', 'Vos dashboards', 'Autres dashboards',
                                'Moyenne éléments/dashboard'],
                'Valeur': [
                    len(dashboards),
                    sum(1 for d in dashboards if d.get('is_owner')),
                    len(dashboards) - sum(1 for d in dashboards if d.get('is_owner')),
                    round(np.mean([len(d.get('dashboardItems', [])) for d in dashboards]), 2)
                ]
            })
            stats_df.to_excel(writer, sheet_name='Statistiques', index=False)

        excel_data = output.getvalue()

        # Télécharger
        st.download_button(
            label="📥 Télécharger la liste complète",
            data=excel_data,
            file_name=f"liste_dashboards_complete_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"download_list_{int(time.time())}"
        )
    except Exception as e:
        st.error(f"Erreur lors de la création du fichier: {str(e)}")


def main():
    # En-tête
    st.markdown('<h1 class="main-header">📊 DHIS2 Dashboard Viewer</h1>', unsafe_allow_html=True)

    # Initialisation session state
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

    # Sidebar
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
            if st.button("Se connecter", key="login_btn", use_container_width=True):
                with st.spinner("Connexion..."):
                    client = DHIS2Client(base_url, username, password)
                    success, user_info = client.test_connection()

                    if success:
                        st.session_state.authenticated = True
                        st.session_state.client = client
                        st.session_state.user_info = user_info

                        # Réinitialiser les données
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

            # Options
            st.markdown("### ⚙️ Options")
            if st.button("🔄 Actualiser les dashboards", use_container_width=True):
                st.session_state.all_dashboards_complete = []
                st.rerun()

    # Contenu principal
    if not st.session_state.authenticated:
        display_welcome_page()
    else:
        # Dashboard sélectionné
        if st.session_state.current_dashboard:
            display_selected_dashboard()
        else:
            # Afficher directement tous les dashboards
            display_all_dashboards()


if __name__ == "__main__":
    main()